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
from pathlib import Path

from novel_parser import NovelTextParser, NotelProjectParser, ParsedNovel
from scene_detector import detect_scenes
from yaml_exporter import (
    Beat,
    BeatExtensions,
    Character,
    Episode,
    ManjuExtensions,
    Metadata,
    Scene,
    SceneHeading,
    ScriptDocument,
    ScriptRoot,
    Sequence,
    validate_yaml_file,
)


# =============================================================================
# 集数自动规划算法（漫剧专用）
# =============================================================================

MANJU_TARGET_DURATION_SECONDS = 240  # 默认每集目标 4 分钟
MANJU_MIN_DURATION_SECONDS = 180     # 每集最少 3 分钟
MANJU_MAX_DURATION_SECONDS = 300     # 每集最多 5 分钟


def plan_episodes(scenes: list[Scene]) -> list[Episode]:
    """
    将场景列表自动规划为漫剧集数。

    策略：
    1. 按 scene 顺序累加时长
    2. 当累计时长达到目标区间 [3min, 5min] 时，尝试在此处切分
    3. 优先在 scene 边界切分，不在 scene 中间切分
    4. 每集必须包含至少 1 个 scene
    """
    if not scenes:
        return []

    episodes: list[Episode] = []
    current_scenes: list[str] = []
    current_duration = 0
    ep_number = 0

    for scene in scenes:
        sc_duration = scene.estimated_duration_seconds or 60
        would_be = current_duration + sc_duration

        # 判断是否应该切分
        should_split = False
        if current_scenes:
            # 如果加入当前 scene 后超过最大时长，必须切分
            if would_be > MANJU_MAX_DURATION_SECONDS:
                should_split = True
            # 如果已经达到目标时长区间，且当前 scene 是一个合理的切分点
            elif current_duration >= MANJU_TARGET_DURATION_SECONDS:
                should_split = True
            # 特殊：如果当前 scene 是 transition/montage 类型，适合作为集末过渡
            elif scene.type in ("transition", "montage") and current_duration >= MANJU_MIN_DURATION_SECONDS:
                should_split = True

        if should_split:
            # 保存当前集
            ep_number += 1
            episodes.append(_build_episode(ep_number, current_scenes, scenes))
            current_scenes = [scene.scene_id]
            current_duration = sc_duration
        else:
            current_scenes.append(scene.scene_id)
            current_duration = would_be

    # 最后一集
    if current_scenes:
        ep_number += 1
        episodes.append(_build_episode(ep_number, current_scenes, scenes))

    return episodes


def _build_episode(ep_number: int, scene_ids: list[str], all_scenes: list[Scene]) -> Episode:
    """构建单集对象"""
    # 计算集时长
    duration = sum(
        sc.estimated_duration_seconds or 60
        for sc in all_scenes
        if sc.scene_id in scene_ids
    )

    # 计算来源章节
    source_chapters: set[int] = set()
    for sc in all_scenes:
        if sc.scene_id in scene_ids and sc.source_chapters:
            source_chapters.update(sc.source_chapters)

    # 生成 hook：取最后一幕的情绪或最后一个 beat 的内容作为钩子提示
    hook = ""
    for sc in reversed(all_scenes):
        if sc.scene_id in scene_ids:
            if sc.mood:
                hook = f"{sc.mood} — 待设计悬念卡点"
            elif sc.beats:
                last_beat = sc.beats[-1]
                if last_beat.type == "dialogue":
                    hook = f"台词卡点：'{last_beat.content[:20]}...'"
                else:
                    hook = f"动作卡点：'{last_beat.content[:20]}...'"
            break

    return Episode(
        episode_id=f"ep_{ep_number:02d}",
        episode_number=ep_number,
        title=f"第{ep_number}集",
        hook=hook or "待设计悬念钩子",
        target_duration_seconds=min(max(duration, MANJU_MIN_DURATION_SECONDS), MANJU_MAX_DURATION_SECONDS),
        source_chapters=sorted(source_chapters) if source_chapters else None,
        scenes=scene_ids,
    )


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
) -> ScriptDocument:
    """核心转换流程：小说 -> 剧本"""
    print(f"[1/4] 加载小说: {novel.title} ({len(novel.chapters)} 章)")

    # 1. 场景检测
    print(f"[2/4] 场景检测（模式: {mode}）...")
    detection_results = detect_scenes(novel, mode=mode, api_key=api_key)
    total_scenes = sum(len(r.scenes) for r in detection_results)
    print(f"       检测到 {total_scenes} 个场景")

    # 2. 构建角色表
    characters = _build_characters(novel)

    # 3. 构建 Sequence 和 Scene
    sequences, scenes = _build_sequences_and_scenes(detection_results, novel, characters, script_type, panel_mode)

    # 4. 漫剧：自动规划集数
    episodes = None
    if script_type == "manju":
        print("[3/4] 漫剧集数规划...")
        episodes = plan_episodes(scenes)
        print(f"       规划为 {len(episodes)} 集（目标每集 3-5 分钟）")
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
        script_type=script_type,  # type: ignore[arg-type]
        title=novel.title or "未命名剧本",
        source=str(novel.source_path) if novel.source_path else None,
        metadata=metadata,
        characters=characters,
        sequences=sequences,
        episodes=episodes,
        scenes=scenes,
    )

    suffix = f", {len(episodes)} 集" if episodes else ""
    print(f"[4/4] 构建完成: {len(scenes)} 场景, {total_beats} 节拍{suffix}")
    return ScriptDocument(script=script_root)


def _build_characters(novel: ParsedNovel) -> list[Character]:
    """从小说解析结果构建角色表"""
    characters: list[Character] = []
    if novel.characters:
        for nc in novel.characters:
            # 生成英文 snake_case id
            char_id = nc.name.strip("女主：男主：")
            char_id = char_id.split("（")[0].split("[")[0].strip()
            char_id = char_id.lower().replace(" ", "_")[:20]
            # 确保 id 不为空
            if not char_id:
                char_id = f"char_{len(characters)+1}"

            characters.append(Character(
                id=char_id,
                name=nc.name,
                aliases=nc.aliases or [],
                description=nc.description or "",
                voice_tags=nc.voice_tags or [],
                archetype=nc.archetype or "",
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

    for result in detection_results:
        for detected_scene in result.scenes:
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

                # 填充 extensions
                extensions = BeatExtensions()
                if script_type == "screenplay":
                    from yaml_exporter import ScreenplayExtensions
                    extensions.screenplay = ScreenplayExtensions()
                elif script_type == "audio_drama":
                    from yaml_exporter import AudioDramaExtensions
                    extensions.audio_drama = AudioDramaExtensions()
                elif script_type == "stage_play":
                    from yaml_exporter import StagePlayExtensions
                    extensions.stage_play = StagePlayExtensions()
                elif script_type == "manju":
                    extensions.manju = _build_manju_extensions(db, panel_mode)

                # 匹配 character ID
                char_id: str | None = None
                if db.character:
                    for c in characters:
                        if c.name == db.character or db.character in c.aliases:
                            char_id = c.id
                            break

                beats.append(Beat(
                    beat_id=b_id,
                    type=db.type,
                    character=char_id,
                    content=db.content,
                    parenthetical=db.parenthetical,
                    extensions=extensions,
                ))

            scenes.append(Scene(
                scene_id=sc_id,
                sequence_id=seq_id,
                heading=SceneHeading(
                    int_ext=detected_scene.heading_int_ext,  # type: ignore[arg-type]
                    location=detected_scene.heading_location,
                    time=detected_scene.heading_time,
                ),
                source_chapters=detected_scene.source_chapters,
                estimated_duration_seconds=detected_scene.estimated_duration_seconds,
                type=detected_scene.scene_type,  # type: ignore[arg-type]
                mood=detected_scene.mood,
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


def _build_manju_extensions(db, panel_mode: str) -> ManjuExtensions:
    """构建漫剧扩展字段"""
    ext = ManjuExtensions()

    # 通用：景别推断
    content_len = len(db.content)
    if content_len <= 15:
        ext.shot = "EXTREME_CLOSE-UP"
    elif content_len <= 30:
        ext.shot = "CLOSE-UP"
    elif content_len <= 60:
        ext.shot = "MEDIUM"
    else:
        ext.shot = "WIDE"

    # 详细模式：画面描述
    if panel_mode == "detailed":
        ext.frame_description = db.content
        if db.type == "dialogue":
            ext.dialogue_bubble = "右下"  # 默认右下角
            ext.sfx_visual = []
        elif db.type == "action":
            # 尝试提取动作中的拟声词
            import re
            sfx_matches = re.findall(r"[砰咔嚓轰咚嗖唰哗叮咚吱呀]+", db.content)
            if sfx_matches:
                ext.sfx_visual = sfx_matches

    # 对白类型的配音指导
    if db.type == "dialogue":
        if db.parenthetical:
            ext.voice_direction = db.parenthetical.strip("（）")
        else:
            ext.voice_direction = "按角色 voice_tags 演绎"

    # 默认转场和特效为空（留空提示策略）
    ext.transition = None
    ext.visual_effect = None
    ext.effect_note = None
    ext.bgm = None
    ext.sfx = None
    ext.subtitle_style = "BUBBLE" if db.type == "dialogue" else "NORMAL"
    ext.duration_seconds = 2.0 if db.type == "dialogue" else 3.0

    return ext


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
