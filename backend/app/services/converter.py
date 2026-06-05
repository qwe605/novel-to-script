"""
转换服务：封装现有 scripts/ 的转换逻辑，供 FastAPI 调用。
"""

import sys
import uuid
from pathlib import Path

# 将 scripts 目录加入 Python 路径，以便复用现有模块
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

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
from novel_to_script import (
    _build_characters,
    _build_sequences_and_scenes,
    plan_episodes,
)


def convert_novel(
    input_path: Path,
    script_type: str,
    mode: str,
    panel_mode: str,
    api_key: str | None,
    ai_config: dict | None = None,
) -> ScriptDocument:
    """
    核心转换接口：接收上传的文件/目录路径，返回 ScriptDocument。

    ai_config 可选字段:
        provider, model, base_url, temperature, max_tokens, top_p, system_prompt
    """
    # 自动检测源类型
    if input_path.is_dir():
        if (input_path / "正文.md").exists() or (input_path / "设定.md").exists():
            source_type = "notel"
        else:
            source_type = "notel"
    else:
        source_type = "text"

    # 加载小说
    if source_type == "notel":
        novel = NotelProjectParser(input_path).parse()
    else:
        parser = NovelTextParser()
        chapters = parser.parse_file(input_path)
        novel = ParsedNovel(
            title=input_path.stem,
            source_path=input_path,
            chapters=chapters,
        )

    if not novel.chapters:
        raise ValueError("未能解析到任何章节")

    # 场景检测（传入完整 AI 配置）
    ai_cfg = ai_config or {}
    detection_results = detect_scenes(
        novel,
        mode=mode,
        api_key=api_key,
        provider=ai_cfg.get("provider", "deepseek"),
        model=ai_cfg.get("model"),
        base_url=ai_cfg.get("base_url"),
        temperature=float(ai_cfg.get("temperature", 0.7)),
        max_tokens=int(ai_cfg.get("max_tokens", 4096)),
    )

    # 构建角色表
    characters = _build_characters(novel)

    # 构建 Sequence 和 Scene
    sequences, scenes = _build_sequences_and_scenes(
        detection_results, novel, characters, script_type, panel_mode
    )

    # 漫剧集数规划
    episodes = None
    if script_type == "manju":
        episodes = plan_episodes(scenes)

    # 计算 metadata
    total_beats = sum(len(s.beats) for s in scenes)
    est_duration = sum(s.estimated_duration_seconds or 0 for s in scenes) / 60.0

    metadata = Metadata(
        total_scenes=len(scenes),
        total_beats=total_beats,
        total_episodes=len(episodes) if episodes else None,
        estimated_duration_minutes=round(est_duration, 1),
        adapted_by="AI 辅助改编（novel-to-script Web）",
        adaptation_notes=f"模式：{mode} | 类型：{script_type} | 来源章节数：{len(novel.chapters)}",
    )

    # 组装 ScriptDocument
    script_root = ScriptRoot(
        version="1.0",
        script_type=script_type,
        title=novel.title or "未命名剧本",
        source=str(novel.source_path) if novel.source_path else None,
        metadata=metadata,
        characters=characters,
        sequences=sequences,
        episodes=episodes,
        scenes=scenes,
    )

    return ScriptDocument(script=script_root)
