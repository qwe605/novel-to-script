"""
转换服务：封装现有 scripts/ 的转换逻辑，供 FastAPI 调用。
拆分为 load_novel()（同步加载）+ run_pipeline()（异步后台用）两步。
"""

import sys
from pathlib import Path
from typing import Callable

# 将 scripts 目录加入 Python 路径，以便复用现有模块
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from novel_parser import NovelTextParser, NotelProjectParser, ParsedNovel
from yaml_exporter import ScriptDocument
from novel_to_script import generate_script


# 有效的转换参数范围
VALID_SCRIPT_TYPES = ("manju", "screenplay", "audio_drama", "stage_play")
VALID_MODES = ("rule", "ai")
VALID_PANEL_MODES = ("simple", "detailed")


def load_novel(input_path: Path) -> ParsedNovel:
    """校验输入并加载小说（同步，速度很快 — 仅文件 I/O）"""
    if input_path is None:
        raise ValueError("input_path 不能为空")
    if not isinstance(input_path, Path):
        input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"输入路径不存在: {input_path}")

    source_type = "notel" if input_path.is_dir() else "text"

    try:
        if source_type == "notel":
            novel = NotelProjectParser(input_path).parse()
        else:
            parser = NovelTextParser()
            chapters = parser.parse_file(input_path)
            novel = ParsedNovel(title=input_path.stem, source_path=input_path, chapters=chapters)
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

    if not novel.title or novel.title.strip() == "":
        novel.title = input_path.stem or "未命名作品"

    return novel


def run_pipeline(
    *,
    input_path: Path,
    script_type: str,
    mode: str,
    panel_mode: str,
    title: str | None = None,
    api_key: str | None = None,
    ai_config: dict | None = None,
    episode_config: dict | None = None,
    on_progress: Callable[[str, float], None] | None = None,
    timing_log: dict[str, float] | None = None,
) -> ScriptDocument:
    """
    执行完整转换管线（供后台任务调用）。

    流程：
        1. load_novel() 加载小说
        2. generate_script() 场景检测 → 剧本构建（可传入 on_progress 回调）
        3. 返回 ScriptDocument

    on_progress(phase: str, progress: float 0-1) 在关键阶段回调。
    """
    # ---- 参数校验 ----
    if script_type not in VALID_SCRIPT_TYPES:
        raise ValueError(f"不支持的剧本类型: {script_type}")
    if mode not in VALID_MODES:
        raise ValueError(f"不支持的转换模式: {mode}")
    if panel_mode not in VALID_PANEL_MODES:
        raise ValueError(f"不支持的分镜模式: {panel_mode}")

    # ---- 加载 ----
    novel = load_novel(input_path)

    # ---- 转换 ----
    if title and title.strip():
        novel.title = title.strip()

    ai_cfg = ai_config or {}

    try:
        return generate_script(
            novel=novel,
            script_type=script_type,
            mode=mode,
            panel_mode=panel_mode,
            api_key=api_key,
            provider=ai_cfg.get("provider", "deepseek"),
            model=ai_cfg.get("model"),
            base_url=ai_cfg.get("base_url"),
            temperature=float(ai_cfg.get("temperature", 0.7)),
            max_tokens=int(ai_cfg.get("max_tokens", 4096)),
            episode_config=episode_config,
            verbose=False,
            on_progress=on_progress,
            timing_log=timing_log,
        )
    except ImportError as e:
        raise RuntimeError(f"缺少 AI 依赖库: {e}。AI 模式请安装: pip install anthropic openai") from e
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        raise RuntimeError(f"转换失败: {e}\n\n完整堆栈:\n{tb}") from e


def convert_novel(
    input_path: Path,
    script_type: str,
    mode: str,
    panel_mode: str,
    api_key: str | None,
    ai_config: dict | None = None,
    episode_config: dict | None = None,
) -> ScriptDocument:
    """
    同步转换接口（向后兼容 — CLI / 内部调用）。
    等同于 run_pipeline() 但不带 on_progress。
    """
    return run_pipeline(
        input_path=input_path,
        script_type=script_type,
        mode=mode,
        panel_mode=panel_mode,
        api_key=api_key,
        ai_config=ai_config,
        episode_config=episode_config,
    )
