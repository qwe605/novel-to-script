"""
转换服务：封装现有 scripts/ 的转换逻辑，供 FastAPI 调用。
"""

import sys
import uuid
from pathlib import Path

# 将 scripts 目录加入 Python 路径，以便复用现有模块
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
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


# 有效的转换参数范围
VALID_SCRIPT_TYPES = ("manju", "screenplay", "audio_drama", "stage_play")
VALID_MODES = ("rule", "ai")
VALID_PANEL_MODES = ("simple", "detailed")


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
    # ------ 输入校验 ------
    if input_path is None:
        raise ValueError("input_path 不能为空")
    if not isinstance(input_path, Path):
        input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"输入路径不存在: {input_path}")
    if script_type not in VALID_SCRIPT_TYPES:
        raise ValueError(f"不支持的剧本类型: {script_type}，有效值: {VALID_SCRIPT_TYPES}")
    if mode not in VALID_MODES:
        raise ValueError(f"不支持的转换模式: {mode}，有效值: {VALID_MODES}")
    if panel_mode not in VALID_PANEL_MODES:
        raise ValueError(f"不支持的分镜模式: {panel_mode}，有效值: {VALID_PANEL_MODES}")

    # ------ 自动检测源类型 ------
    if input_path.is_dir():
        if (input_path / "正文.md").exists() or (input_path / "设定.md").exists():
            source_type = "notel"
        else:
            source_type = "notel"
    else:
        source_type = "text"

    # ------ 加载小说 ------
    try:
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
    except UnicodeDecodeError:
        raise ValueError(f"文件编码不支持，请使用 UTF-8 编码: {input_path}")
    except PermissionError:
        raise PermissionError(f"无法读取文件，权限不足: {input_path}")
    except IsADirectoryError:
        raise IsADirectoryError(f"需要文件路径但收到了目录，请直接上传 .txt/.md 文件: {input_path}")
    except Exception as e:
        raise RuntimeError(f"加载小说失败: {e}") from e

    if not novel:
        raise RuntimeError("小说解析结果为空")
    if not novel.chapters:
        if source_type == "text" and input_path.stat().st_size == 0:
            raise ValueError(f"文件为空: {input_path}")
        raise ValueError("未能解析到任何章节，请确认文件包含有效的章节分隔符")

    # ------ 标题补全 ------
    if not novel.title or novel.title.strip() == "":
        novel.title = input_path.stem or "未命名作品"

    # ------ 场景检测（传入完整 AI 配置）------
    ai_cfg = ai_config or {}
    try:
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
    except ImportError as e:
        raise RuntimeError(f"缺少 AI 依赖库: {e}。AI 模式请安装: pip install anthropic openai")
    except Exception as e:
        raise RuntimeError(f"场景检测失败: {e}") from e

    if not detection_results:
        raise RuntimeError("场景检测无结果，请检查输入文件内容")

    # ------ 构建角色表 ------
    characters = _build_characters(novel)
    if not characters:
        characters = [
            Character(
                id="protagonist",
                name="主角",
                description="请根据小说设定补充角色信息",
            )
        ]

    # ------ 构建 Sequence 和 Scene ------
    sequences, scenes = _build_sequences_and_scenes(
        detection_results, novel, characters, script_type, panel_mode
    )
    if not scenes:
        raise RuntimeError("未能构建任何场景，请确认小说包含可解析的内容")

    # ------ 漫剧集数规划 ------
    episodes = None
    if script_type == "manju":
        episodes = plan_episodes(scenes)
        if not episodes:
            episodes = []

    # ------ 计算 metadata ------
    total_beats = sum(len(s.beats) for s in scenes)
    est_duration = sum(s.estimated_duration_seconds or 0 for s in scenes) / 60.0
    est_duration = max(round(est_duration, 1), 0.1)

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
