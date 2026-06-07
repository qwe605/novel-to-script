#!/usr/bin/env python3
"""
Novel-to-Script CLI 主入口

核心场景：网文漫剧（动态漫画/有声漫画），同时兼容影视剧本、广播剧、舞台剧。

用法示例:
    # 转换 notel 项目（漫剧模式，自动分集）
    python novel_to_script.py --input "穿成病娇大佬的亡妻" --script-type manju

    # 漫剧详细分镜模式
    python novel_to_script.py --input "novel.txt" --script-type manju --panel-mode detailed

    # 影视剧本
    python novel_to_script.py --input "穿成病娇大佬的亡妻" --script-type screenplay

    # AI 深度模式
    python novel_to_script.py --input "novel.txt" --mode ai --script-type manju
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Callable, cast

from novel_parser import NovelTextParser, NotelProjectParser, ParsedNovel
from scene_detector import detect_scenes, extract_characters_with_ai
from yaml_exporter import (
    Beat,
    BeatExtensions,
    Character,
    CharacterRelationship,
    Episode,
    IntExt,
    ManjuExtensions,
    Metadata,
    Scene,
    SceneHeading,
    SceneType,
    ScriptDocument,
    ScriptRoot,
    ScriptType,
    Sequence,
    validate_yaml_file,
)


# =============================================================================
# 集数自动规划算法（漫剧专用）
# =============================================================================

# =============================================================================
# 集数自动规划算法（漫剧专用）—— 默认值
# =============================================================================

MANJU_DEFAULT_MIN = 180    # 每集最少 3 分钟
MANJU_DEFAULT_MAX = 300    # 每集最多 5 分钟
MANJU_DEFAULT_TARGET = 240 # 默认每集目标 4 分钟

# 钩子风格 → UI 标签
_HOOK_STYLE_LABELS: dict[str, str] = {
    "cliffhanger": "悬念卡点",
    "twist":       "反转时刻",
    "emotional":   "情感钩子",
    "suspense":    "悬疑卡点",
    "action":      "行动卡点",
}


def plan_episodes(
    scenes: list[Scene],
    min_duration: int = MANJU_DEFAULT_MIN,
    max_duration: int = MANJU_DEFAULT_MAX,
    target_episodes: int | None = None,
    hook_style: str = "cliffhanger",
    title_template: str = "第{n}集",
    auto_split: bool = True,
    chapters_map: dict[int, str] | None = None,
) -> list[Episode]:
    """将场景列表规划为漫剧集数。"""
    if not scenes:
        return []

    cm = chapters_map or {}

    if not auto_split:
        return [_single_episode(1, scenes, hook_style, title_template, min_duration, max_duration, cm)]

    if target_episodes and target_episodes > 0:
        return _split_by_count(scenes, target_episodes, hook_style, title_template, min_duration, max_duration, cm)

    return _split_by_duration(scenes, MANJU_DEFAULT_TARGET, min_duration, max_duration, hook_style, title_template, cm)


def _single_episode(
    ep_number: int, episode_scenes: list[Scene],
    hook_style: str, title_template: str,
    min_duration: int, max_duration: int,
    chapters_map: dict[int, str] | None = None,
) -> Episode:
    """所有场景合并为单集"""
    eps = episode_scenes or []
    scene_ids = [s.scene_id for s in eps]
    total = sum(getattr(s, "estimated_duration_seconds", 0) or 60 for s in eps)
    src = sorted({ch for s in eps for ch in (getattr(s, "source_chapters", None) or [])}) or None
    return Episode(
        episode_id=f"ep_{ep_number:02d}", episode_number=ep_number,
        title=_format_title(title_template, ep_number,
            _episode_subtitle(eps, [s.scene_id for s in eps], chapters_map or {})),
        hook=_generate_hook_text(eps, scene_ids, hook_style),
        target_duration_seconds=min(max(total, min_duration), max_duration),
        source_chapters=src, scenes=scene_ids,
    )


def _split_by_count(
    scenes: list[Scene], n: int,
    hook_style: str, title_template: str,
    min_duration: int, max_duration: int,
    chapters_map: dict[int, str] | None = None,
) -> list[Episode]:
    """优先在章节边界切分"""
    if not scenes:
        return []
    cm = chapters_map or {}
    ep_count = min(n, len(scenes))

    # 收集每个章节的场景 ID 列表
    seen: dict[int, list[str]] = {}
    for sc in (scenes or []):
        ch = (sc.source_chapters or [0])[0] if sc.source_chapters else 0
        seen.setdefault(ch, []).append(sc.scene_id)
    chapters_ordered = sorted(seen.items())

    # 单章/无章 → 回退场景均分
    if len(chapters_ordered) <= 1:
        base_sc = len(scenes) // ep_count
        extra_sc = len(scenes) % ep_count
        eps: list[Episode] = []
        idx = 0
        for ep_num in range(ep_count):
            count = base_sc + (1 if ep_num < extra_sc else 0)
            chunk = scenes[idx:idx + count]
            sids = [s.scene_id for s in chunk]
            eps.append(_build_episode(ep_num + 1, sids, scenes, hook_style, title_template, cm))
            idx += count
        return eps

    # 按章均分
    total_chapters = len(chapters_ordered)
    base = total_chapters // ep_count
    extra = total_chapters % ep_count

    episodes = []
    ch_idx = 0
    for ep_num in range(ep_count):
        count = base + (1 if ep_num < extra else 0)
        chunk_chapters = chapters_ordered[ch_idx:ch_idx + count]
        sids = [sid for _, sids in chunk_chapters for sid in sids]
        episodes.append(_build_episode(ep_num + 1, sids, scenes, hook_style, title_template, cm))
        ch_idx += count

    return episodes


def _split_by_duration(
    scenes: list[Scene],
    target_per_ep: int, min_duration: int, max_duration: int,
    hook_style: str, title_template: str,
    chapters_map: dict[int, str] | None = None,
) -> list[Episode]:
    """按时长窗口贪心切分"""
    if not scenes:
        return []
    cm = chapters_map or {}
    if not scenes:
        return []
    episodes: list[Episode] = []
    current_scenes: list[str] = []
    current_duration = 0
    ep_number = 0

    for scene in (scenes or []):
        sc_duration = scene.estimated_duration_seconds or 60
        would_be = current_duration + sc_duration

        should_split = False
        if current_scenes:
            if would_be > max_duration:
                should_split = True
            elif current_duration >= target_per_ep:
                should_split = True
            elif scene.type in ("transition", "montage") and current_duration >= min_duration // 2:
                should_split = True

        if should_split:
            ep_number += 1
            episodes.append(_build_episode(ep_number, current_scenes, scenes, hook_style, title_template, cm))
            current_scenes = [scene.scene_id]
            current_duration = sc_duration
        else:
            current_scenes.append(scene.scene_id)
            current_duration = would_be

    if current_scenes:
        ep_number += 1
        episodes.append(_build_episode(ep_number, current_scenes, scenes, hook_style, title_template, cm))

    return episodes


def _build_episode(
    ep_number: int,
    scene_ids: list[str],
    all_scenes: list[Scene],
    hook_style: str = "cliffhanger",
    title_template: str = "第{n}集",
    chapters_map: dict[int, str] | None = None,
) -> Episode:
    """构建单集对象（支持标题模板和钩子风格）"""
    # 计算集时长
    duration = sum(
        (getattr(sc, "estimated_duration_seconds", 0) or 60)
        for sc in (all_scenes or [])
        if getattr(sc, "scene_id", None) in (scene_ids or [])
    )

    # 计算来源章节
    source_chapters: set[int] = set()
    for sc in (all_scenes or []):
        if getattr(sc, "scene_id", None) in (scene_ids or []) and getattr(sc, "source_chapters", None):
            source_chapters.update(sc.source_chapters)

    # 生成 hook
    hook = _generate_hook_text(all_scenes, scene_ids, hook_style)

    # 字幕：优先首个场景的章节标题，否则 mood，否则章节范围
    subtitle = _episode_subtitle(all_scenes, scene_ids, chapters_map)

    title = _format_title(title_template, ep_number, subtitle)

    return Episode(
        episode_id=f"ep_{ep_number:02d}",
        episode_number=ep_number,
        title=title,
        hook=hook or "待设计悬念钩子",
        target_duration_seconds=min(max(duration, MANJU_DEFAULT_MIN), MANJU_DEFAULT_MAX),
        source_chapters=sorted(source_chapters) if source_chapters else None,
        scenes=scene_ids,
    )


def _chapter_range_label(chapters: set[int]) -> str:
    """将章节集合转为可读标签：{1,2,3} → '第1-3章'"""
    if not chapters:
        return ""
    sorted_chs = sorted(chapters)
    if len(sorted_chs) == 1:
        return f"第{sorted_chs[0]}章"
    if sorted_chs == list(range(sorted_chs[0], sorted_chs[-1] + 1)):
        return f"第{sorted_chs[0]}-{sorted_chs[-1]}章"
    return f"第{sorted_chs[0]}~{sorted_chs[-1]}章"


def _episode_subtitle(all_scenes: list, scene_ids: list[str], chapters_map: dict[int, str]) -> str:
    """生成意的集标题字幕：优先章节标题 → 场景情绪 → 来源范围"""
    # 1) 从首个场景的章节号找章节标题
    first_ch: int | None = None
    for sc in (all_scenes or []):
        if getattr(sc, "scene_id", None) in (scene_ids or []):
            src = getattr(sc, "source_chapters", None) or []
            if src:
                first_ch = src[0]
                break

    if first_ch and first_ch in chapters_map:
        ch_title = chapters_map[first_ch]
        if ch_title and len(ch_title) <= 12:
            return ch_title

    # 2) 使用首个场景的 mood
    for sc in (all_scenes or []):
        if getattr(sc, "scene_id", None) in (scene_ids or []):
            mood = getattr(sc, "mood", None)
            if mood and "→" in mood:
                return mood.split("→")[0][:6]
            if mood and mood.strip():
                return mood[:8]
            break

    # 3) 回退：章节范围
    source_chapters: set[int] = set()
    for sc in (all_scenes or []):
        if getattr(sc, "scene_id", None) in (scene_ids or []):
            src = getattr(sc, "source_chapters", None) or []
            source_chapters.update(src)
    return _chapter_range_label(source_chapters)


def _generate_hook_text(
    all_scenes: list[Scene],
    scene_ids: list[str],
    hook_style: str,
) -> str:
    """根据钩子风格生成集末卡点文本"""
    label = _HOOK_STYLE_LABELS.get(hook_style, "悬念卡点")

    for sc in reversed(all_scenes or []):
        if getattr(sc, "scene_id", None) in (scene_ids or set()):
            mood = getattr(sc, "mood", None)
            if mood:
                return f"{label}：{mood} — 待设计"
            beats = getattr(sc, "beats", None) or []
            if beats:
                last_beat = beats[-1]
                bt = getattr(last_beat, "type", "action") or "action"
                bc = getattr(last_beat, "content", "") or ""
                prefix = "台词" if bt == "dialogue" else "动作"
                return f"{label}：{prefix}卡点 '{bc[:20]}...'"
            break
    return f"{label}：待设计"


def _format_title(title_template: str, n: int, subtitle: str) -> str:
    """格式化集标题模板，支持 {n} {subtitle} {pause}"""
    result = title_template.replace("{n}", str(n))
    result = result.replace("{subtitle}", subtitle)
    result = result.replace("{pause}", "·")
    return result


# =============================================================================
# CLI
# =============================================================================

def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="novel_to_script",
        description="将小说文本自动转换为结构化剧本（YAML 格式）。核心场景：网文漫剧。",
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="输入路径：notel 项目目录 或 小说文本文件",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出 YAML 文件路径（默认：{书名}/剧本/{书名}_剧本.yaml）",
    )
    parser.add_argument(
        "--script-type", "-t",
        choices=["screenplay", "audio_drama", "stage_play", "manju"],
        default="manju",
        help="剧本类型（默认：manju 网文漫剧）",
    )
    parser.add_argument(
        "--source-type", "-s",
        choices=["auto", "notel", "text"],
        default="auto",
        help="输入源类型（默认：auto，自动检测）",
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["rule", "ai"],
        default="rule",
        help="场景检测模式：rule（规则，零成本）或 ai（AI 深度，需要 API Key）",
    )
    parser.add_argument(
        "--panel-mode",
        choices=["simple", "detailed"],
        default="simple",
        help="【漫剧】画面描述粒度：simple（文字分镜）或 detailed（标准漫画分镜格）",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Anthropic API Key（AI 模式使用，也可通过 ANTHROPIC_API_KEY 环境变量设置）",
    )
    parser.add_argument(
        "--validate", "-v",
        action="store_true",
        help="输出后执行 Schema 校验",
    )
    return parser


def detect_source_type(input_path: Path) -> str:
    """自动检测输入源类型"""
    if input_path.is_dir():
        if (input_path / "正文.md").exists() or (input_path / "设定.md").exists():
            return "notel"
        return "notel"
    else:
        return "text"


def load_novel(input_path: Path, source_type: str) -> ParsedNovel:
    """加载小说数据"""
    if source_type == "notel":
        parser = NotelProjectParser(input_path)
        return parser.parse()
    else:
        parser = NovelTextParser()
        chapters = parser.parse_file(input_path)
        return ParsedNovel(
            title=input_path.stem,
            source_path=input_path,
            chapters=chapters,
        )


def generate_script(
    novel: ParsedNovel,
    script_type: str,
    mode: str,
    api_key: str | None,
    panel_mode: str = "simple",
    provider: str = "deepseek",
    model: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    episode_config: dict | None = None,
    verbose: bool = True,
    on_progress: "Callable[[str, float], None] | None" = None,
    timing_log: dict[str, float] | None = None,
) -> ScriptDocument:
    """
    核心转换流程：小说 → 剧本。

    参数:
        novel: 解析后的小说对象
        script_type: 剧本类型 (manju/screenplay/audio_drama/stage_play)
        mode: 检测模式 (rule/ai)
        api_key: AI 模式专用 API Key（也可通过环境变量）
        panel_mode: 漫剧画面粒度 (simple/detailed)
        provider/model/base_url/temperature/max_tokens: AI 提供商配置
        episode_config: 分集配置 dict
        verbose: 是否打印进度信息（CLI=True, Web=False）
        on_progress: 进度回调 (phase: str, progress: float 0-1)
        timing_log: 可变 dict，生成完成后填入各阶段耗时（秒）
    """
    _t0 = time.time()

    def _progress(phase: str, pct: float):
        if on_progress:
            on_progress(phase, pct)
        if verbose:
            print(f"       [{pct:.0%}] {phase}")

    def _lap(name: str):
        """记录当前阶段耗时"""
        now = time.time()
        elapsed = now - _t0
        if timing_log is not None:
            timing_log[name] = round(elapsed, 2)

    _progress("加载小说", 0.05)
    if verbose:
        print(f"[1/4] 加载小说: {novel.title} ({len(novel.chapters)} 章)")

    # 1. 场景检测（传入完整 AI 配置）
    if verbose:
        print(f"[2/4] 场景检测（模式: {mode}）...")
    _t_phase = time.time()
    _progress("场景检测", 0.10)
    t0 = time.time()
    detection_results = detect_scenes(
        novel,
        mode=mode,
        api_key=api_key,
        provider=provider,
        model=model,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    _lap("场景检测")
    if verbose:
        print(f"       [场景检测耗时 {time.time()-t0:.1f}s]")

    total_scenes = sum(len(r.scenes) for r in detection_results)
    if verbose:
        print(f"       检测到 {total_scenes} 个场景")

    # 2. AI 角色提取（AI 模式下，若没有设定或角色信息不完整则自动提取）
    t0 = time.time()
    _progress("角色提取与分析", 0.45)
    if mode == "ai" and api_key:
        # 判断是否需要 AI 提取：没有角色，或角色缺少性格/关系等深度信息
        need_ai_extraction = (
            not novel.characters
            or all(
                not (getattr(c, "personality_traits", None) or getattr(c, "relationships", None))
                for c in novel.characters
            )
        )
        if need_ai_extraction:
            try:
                if verbose:
                    print(f"       [AI 角色特征提取中...]")
                ai_characters = extract_characters_with_ai(
                    novel,
                    api_key=api_key,
                    provider=provider,
                    model=model,
                    base_url=base_url,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if ai_characters:
                    # 合并：保留已有设定中的角色名，用 AI 补充深度特征
                    if novel.characters:
                        existing_names = {c.name for c in novel.characters}
                        for ac in ai_characters:
                            if ac.name not in existing_names:
                                novel.characters.append(ac)
                            else:
                                # 用 AI 提取的特征补充已有角色（不覆盖已有字段）
                                for ec in novel.characters:
                                    if ec.name == ac.name:
                                        if not ec.personality_traits and ac.personality_traits:
                                            ec.personality_traits = ac.personality_traits
                                        if not ec.relationships and ac.relationships:
                                            ec.relationships = ac.relationships
                                        if not ec.role and ac.role:
                                            ec.role = ac.role
                                        if not ec.appearance and ac.appearance:
                                            ec.appearance = ac.appearance
                                        break
                    else:
                        novel.characters = ai_characters
                    if verbose:
                        print(f"       [AI 提取了 {len(ai_characters)} 个角色]")
            except Exception as e:
                if verbose:
                    print(f"       [AI 角色提取失败，使用已有设定: {e}]")

    # 3. 构建角色表
    _progress("构建角色表", 0.50)
    characters = _build_characters(novel)
    _lap("角色提取")
    if verbose:
        print(f"       [角色表构建耗时 {time.time()-t0:.1f}s]")

    # 4. 构建 Sequence 和 Scene
    t0 = time.time()
    _progress("构建场景结构", 0.60)
    sequences, scenes = _build_sequences_and_scenes(detection_results, novel, characters, script_type, panel_mode)
    _lap("构建场景")
    if verbose:
        print(f"       [场景构建耗时 {time.time()-t0:.1f}s]")

    # 5. 漫剧：集数规划（支持 episode_config）
    t0 = time.time()
    _progress("场景结构完成", 0.75)
    episodes = None

    # 构建章节标题映射 {章号: 标题}
    chapters_map: dict[int, str] = {}
    for ch in novel.chapters:
        if ch.title:
            chapters_map[ch.number] = ch.title

    if script_type == "manju":
        ep_cfg = episode_config or {}
        if ep_cfg.get("enabled", True):
            if verbose:
                min_m = (ep_cfg.get("min_duration_seconds") or MANJU_DEFAULT_MIN) // 60
                max_m = (ep_cfg.get("max_duration_seconds") or MANJU_DEFAULT_MAX) // 60
                print(f"[3/4] 漫剧集数规划...")
            _progress("规划集数", 0.80)
            episodes = plan_episodes(
                scenes,
                min_duration=ep_cfg.get("min_duration_seconds", MANJU_DEFAULT_MIN),
                max_duration=ep_cfg.get("max_duration_seconds", MANJU_DEFAULT_MAX),
                target_episodes=ep_cfg.get("target_episodes"),
                hook_style=ep_cfg.get("hook_style", "cliffhanger"),
                title_template=ep_cfg.get("title_template", "第{n}集"),
                auto_split=ep_cfg.get("auto_split", True),
                chapters_map=chapters_map,
            )
            _lap("规划集数")
            if verbose:
                print(f"       规划为 {len(episodes)} 集（目标每集 {min_m}-{max_m} 分钟）耗时 {time.time()-t0:.1f}s")
                for ep in episodes:
                    print(f"         {ep.episode_id}: {len(ep.scenes)} 场景, "
                          f"目标 {ep.target_duration_seconds}s, 来源章节: {ep.source_chapters}")

    # 5. 计算 metadata
    total_beats = sum(len(s.beats) for s in scenes)
    est_duration = sum(s.estimated_duration_seconds or 0 for s in scenes) / 60.0

    metadata = Metadata(
        total_scenes=len(scenes),
        total_beats=total_beats,
        total_episodes=len(episodes) if episodes else None,
        estimated_duration_minutes=round(est_duration, 1),
        adapted_by="AI 辅助改编（novel-to-script）",
        adaptation_notes=f"模式：{mode} | 类型：{script_type} | 来源章节数：{len(novel.chapters)}",
    )

    # 6. 组装 ScriptDocument
    script_root = ScriptRoot(
        version="1.0",
        script_type=cast(ScriptType, script_type),
        title=novel.title or "未命名剧本",
        source=str(novel.source_path) if novel.source_path else None,
        metadata=metadata,
        characters=characters,
        sequences=sequences,
        episodes=episodes,
        scenes=scenes,
    )

    suffix = f", {len(episodes)} 集" if episodes else ""
    if verbose:
        print(f"[4/4] 构建完成: {len(scenes)} 场景, {total_beats} 镜头{suffix}")
    _progress("保存结果", 0.95)
    _lap("总耗时")
    if verbose and timing_log:
        print(f"\n⏱ 耗时统计:")
        for name, sec in timing_log.items():
            print(f"   {name}: {sec:.1f}s")
    return ScriptDocument(script=script_root)


def _build_characters(novel: ParsedNovel) -> list[Character]:
    """从小说解析结果构建角色表"""
    characters: list[Character] = []
    if novel.characters:
        # 先建立 name→id 映射，用于关系中的 target_id 回填
        name_to_id: dict[str, str] = {}
        temp_chars: list[dict] = []

        for nc in (novel.characters or []):
            if not getattr(nc, "name", None):
                continue
            # 生成英文 snake_case id
            char_id = nc.name.strip("女主：男主：")
            char_id = char_id.split("（")[0].split("[")[0].strip()
            char_id = char_id.lower().replace(" ", "_")[:20]
            if not char_id:
                char_id = f"char_{len(characters)+1}"

            name_to_id[nc.name] = char_id
            # 也注册别名
            for alias in (nc.aliases or []):
                if alias not in name_to_id:
                    name_to_id[alias] = char_id

            temp_chars.append({"nc": nc, "id": char_id})

        # 第二遍：构建 Character（此时 name_to_id 已完整，可回填 target_id）
        for entry in temp_chars:
            nc = entry["nc"]
            char_id = entry["id"]

            # 映射关系 → CharacterRelationship（回填 target_id）
            yaml_rels: list[CharacterRelationship] | None = None
            raw_rels = getattr(nc, "relationships", None) or []
            if raw_rels:
                yaml_rels = []
                for rel in raw_rels:
                    target_name = getattr(rel, "target_name", "") or ""
                    target_id = name_to_id.get(target_name)
                    yaml_rels.append(CharacterRelationship(
                        target_id=target_id,
                        target_name=target_name,
                        relation_type=getattr(rel, "relation_type", "") or "相关",
                        description=getattr(rel, "description", None) or None,
                        intensity=getattr(rel, "intensity", None) or None,
                    ))

            characters.append(Character(
                id=char_id,
                name=nc.name,
                aliases=nc.aliases or None,
                description=nc.description or None,
                voice_tags=nc.voice_tags or None,
                archetype=nc.archetype or None,
                personality_traits=getattr(nc, "personality_traits", None) or None,
                relationships=yaml_rels,
                role=getattr(nc, "role", None) or None,
                appearance=getattr(nc, "appearance", None) or None,
            ))
    else:
        characters.append(Character(
            id="protagonist",
            name="主角",
            description="请根据小说设定补充角色信息",
        ))
    return characters


def _build_sequences_and_scenes(
    detection_results,
    novel: ParsedNovel,
    characters: list[Character],
    script_type: str,
    panel_mode: str,
) -> tuple[list[Sequence], list[Scene]]:
    """构建 Sequence 和 Scene 列表"""
    sequences: list[Sequence] = []
    scenes: list[Scene] = []
    beat_counter = 0
    scene_counter = 0

    # Sequence 按小说章节分组（每 1-3 章一个 Sequence）
    seq_map: dict[str, list[str]] = {}

    for result in (detection_results or []):
        for detected_scene in (result.scenes or []):
            scene_counter += 1
            sc_id = f"sc_{scene_counter:03d}"

            # 确定 sequence_id（按章分 Sequence）
            ch_num = result.chapter_number
            seq_idx = (ch_num - 1) // 3 + 1
            seq_id = f"seq_{seq_idx:02d}"
            if seq_id not in seq_map:
                start_ch = (seq_idx - 1) * 3 + 1
                end_ch = min(start_ch + 2, len(novel.chapters))
                seq_name = f"第{start_ch}-{end_ch}章" if start_ch != end_ch else f"第{start_ch}章"
                seq_map[seq_id] = {
                    "scenes": [],
                    "name": seq_name,
                }
            seq_map[seq_id]["scenes"].append(sc_id)

            beats: list[Beat] = []
            for db in detected_scene.beats:
                beat_counter += 1
                b_id = f"b_{beat_counter:03d}"

                # 填充 extensions — 只对 manju 有实质内容时填充
                extensions = None
                if script_type == "manju":
                    manju_ext = _build_manju_extensions(db, panel_mode)
                    if manju_ext is not None:
                        extensions = BeatExtensions()
                        extensions.manju = manju_ext

                # 匹配 character ID
                char_id: str | None = None
                if getattr(db, "character", None):
                    for c in (characters or []):
                        aliases = c.aliases or []
                        if c.name == db.character or db.character in aliases:
                            char_id = c.id
                            break

                beats.append(Beat(
                    beat_id=b_id,
                    type=getattr(db, "type", "action") or "action",
                    character=char_id,
                    content=getattr(db, "content", "") or "",
                    parenthetical=getattr(db, "parenthetical", None),
                    extensions=extensions,
                ))

            # 收集场景角色（AI 模式有，规则模式可能也有）
            scene_chars = getattr(detected_scene, "characters", None) or None

            scenes.append(Scene(
                scene_id=sc_id,
                sequence_id=seq_id,
                heading=SceneHeading(
                    int_ext=cast(IntExt, detected_scene.heading_int_ext),
                    location=detected_scene.heading_location,
                    time=detected_scene.heading_time,
                ),
                source_chapters=detected_scene.source_chapters,
                characters=scene_chars,
                estimated_duration_seconds=detected_scene.estimated_duration_seconds,
                type=cast(SceneType, detected_scene.scene_type),
                mood=detected_scene.mood or None,
                beats=beats,
            ))

    # 构建 Sequence 列表
    for seq_id, data in seq_map.items():
        sequences.append(Sequence(
            id=seq_id,
            name=f"序列{seq_id[-2:]}：{data['name']}",
            scenes=data["scenes"],
        ))

    return sequences, scenes


def _build_manju_extensions(db, panel_mode: str) -> ManjuExtensions | None:
    """构建漫剧扩展字段。简单模式只填必要字段，详细模式全填。无意义值时返回 None。"""
    db_content = getattr(db, "content", "") or ""
    db_type = getattr(db, "type", "action") or "action"

    ext = ManjuExtensions()
    content_len = len(db_content)

    if panel_mode == "detailed":
        # 详细模式：全量填充
        if content_len <= 15:
            ext.shot = "EXTREME_CLOSE-UP"
        elif content_len <= 30:
            ext.shot = "CLOSE-UP"
        elif content_len <= 60:
            ext.shot = "MEDIUM"
        else:
            ext.shot = "WIDE"

        ext.frame_description = db_content
        if db_type == "dialogue":
            ext.dialogue_bubble = "右下"
            ext.voice_direction = db.parenthetical.strip("（）") if getattr(db, "parenthetical", None) else "按角色 voice_tags 演绎"
            ext.subtitle_style = "BUBBLE"
            ext.duration_seconds = 2.0
        elif db_type == "action":
            import re
            sfx_matches = re.findall(r"[砰咔嚓轰咚嗖唰哗叮咚吱呀]+", db_content)
            if sfx_matches:
                ext.sfx_visual = sfx_matches
            ext.subtitle_style = "NORMAL"
            ext.duration_seconds = 3.0
        return ext

    # 简单模式：只有对白才加扩展（字幕 + 时长），动作省略
    if db_type == "dialogue":
        ext.subtitle_style = "BUBBLE"
        ext.duration_seconds = 2.0
        if getattr(db, "parenthetical", None):
            ext.voice_direction = db.parenthetical.strip("（）")
        return ext

    # action / transition 等 — 不需要扩展
    return None


# =============================================================================
# Main
# =============================================================================

def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误：输入路径不存在: {input_path}", file=sys.stderr)
        return 1

    # 自动检测源类型
    source_type = args.source_type
    if source_type == "auto":
        source_type = detect_source_type(input_path)
        print(f"[INFO] 自动检测到源类型: {source_type}")

    # 确定输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        if source_type == "notel" and input_path.is_dir():
            output_path = input_path / "剧本" / f"{input_path.name}_剧本.yaml"
        else:
            output_path = input_path.with_suffix(".yaml")

    try:
        # 加载
        novel = load_novel(input_path, source_type)
        if not novel.chapters:
            print("错误：未能解析到任何章节", file=sys.stderr)
            return 1

        # 转换
        script_doc = generate_script(
            novel=novel,
            script_type=args.script_type,
            mode=args.mode,
            api_key=args.api_key,
            panel_mode=args.panel_mode,
        )

        # 保存
        output_path.parent.mkdir(parents=True, exist_ok=True)
        script_doc.save(output_path)
        print(f"剧本已保存: {output_path}")

        # 校验
        if args.validate:
            ok, errors = validate_yaml_file(output_path)
            if ok:
                print("[VALIDATE] Schema 校验通过 ✓")
            else:
                print("[VALIDATE] Schema 校验失败:")
                for e in errors:
                    print(f"  - {e}")
                return 2

        return 0

    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    sys.exit(main())
