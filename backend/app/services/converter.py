"""
转换服务：封装现有 scripts/ 的转换逻辑，供 FastAPI 调用。
核心职责：加载小说 → 委托 generate_script() 完成转换。
"""

import sys
from pathlib import Path

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
    核心转换接口：接收上传的文件/目录路径，返回 ScriptDocument。

    流程：
        1. 校验参数
        2. 加载小说（自动检测源类型，notel 项目或纯文本文件）
        3. 委托 generate_script() 完成场景检测→剧本构建
        4. 返回 ScriptDocument

    ai_config 可选字段:
        provider, model, base_url, temperature, max_tokens, top_p, system_prompt

    episode_config 可选字段:
        enabled, target_episodes, min_duration_seconds, max_duration_seconds,
        hook_style, auto_split, title_template, scene_prefix
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

    # ------ 委托 generate_script 完成转换 ------
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
            verbose=False,  # Web API 不打印进度
        )
    except ImportError as e:
        raise RuntimeError(f"缺少 AI 依赖库: {e}。AI 模式请安装: pip install anthropic openai")
    except Exception as e:
        raise RuntimeError(f"转换失败: {e}") from e
