"""
转换 API 路由：文件上传、任务提交、状态查询、结果下载。
"""

import json
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from typing import List

from app.core.config import RESULTS_DIR, UPLOAD_DIR
from app.models.schemas import AIConfig, ConvertRequest, ConvertResponse, EpisodeConfig, EpisodeSummary, TaskStatusResponse
from app.services.converter import convert_novel

router = APIRouter(prefix="/api/convert", tags=["convert"])

# 内存中的任务状态存储（适合单用户本地使用）
_tasks: dict[str, dict] = {}


def _parse_optional_json(raw: str | None, model_cls):
    """安全解析可选 JSON 字段为 Pydantic 模型"""
    if not raw:
        return None
    try:
        return model_cls(**json.loads(raw))
    except (json.JSONDecodeError, TypeError):
        return None


def _merge_chapter_files(files: list[UploadFile], task_id: str) -> str:
    """
    将多个章节文件合并为单个带章节标记的文本文件。
    每个文件自动编号为 ###N. 文件名（不含扩展名）。
    """
    merged_path = UPLOAD_DIR / f"{task_id}_merged.md"
    with open(merged_path, "w", encoding="utf-8") as out:
        for idx, f in enumerate(files, 1):
            name = (f.filename or "章节").rsplit(".", 1)[0]
            out.write(f"\n###{idx}. {name}\n\n")
            content = f.file.read()
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="replace")
            out.write(content.strip() + "\n")
    return str(merged_path)


@router.post("", response_model=ConvertResponse)
async def create_convert_task(
    files: List[UploadFile] = File(...),
    script_type: str = Form("manju"),
    mode: str = Form("rule"),
    panel_mode: str = Form("simple"),
    api_key: str | None = Form(None),
    ai_config: str | None = Form(None),
    episode_config: str | None = Form(None),
):
    """
    提交转换任务：上传 1 个或多个小说文件（.txt/.md/.zip），返回 task_id。

    多文件时自动按上传顺序合并为带章节标记的文本（###1. 文件名）。
    也支持单文件 .zip（notel 项目目录压缩包）。

    新增参数（JSON 字符串）：
    - ai_config: AI 模型配置，如 '{"model":"claude-sonnet-4-6","temperature":0.7}'
    - episode_config: 分集设置，如 '{"target_episodes":12,"hook_style":"cliffhanger"}'
    """
    # 解析嵌套配置
    ai_config_obj = _parse_optional_json(ai_config, AIConfig)
    episode_config_obj = _parse_optional_json(episode_config, EpisodeConfig)

    # 向后兼容：如果顶层 api_key 有值而 ai_config_obj 没有，则合并
    effective_api_key = api_key
    if ai_config_obj and ai_config_obj.api_key:
        effective_api_key = ai_config_obj.api_key
    elif api_key and not ai_config_obj:
        ai_config_obj = AIConfig(api_key=api_key)
    elif api_key and ai_config_obj and not ai_config_obj.api_key:
        ai_config_obj.api_key = api_key

    if not files:
        raise HTTPException(status_code=400, detail="请至少上传 1 个文件")

    task_id = str(uuid.uuid4())

    # 情况 1：单文件 .zip → 解压为 notel 项目目录
    input_path: str | None = None
    if len(files) == 1 and files[0].filename and files[0].filename.endswith(".zip"):
        upload_path = UPLOAD_DIR / f"{task_id}_{files[0].filename}"
        with open(upload_path, "wb") as f:
            shutil.copyfileobj(files[0].file, f)
        extract_dir = UPLOAD_DIR / task_id
        with zipfile.ZipFile(upload_path, "r") as z:
            z.extractall(extract_dir)
        items = list(extract_dir.iterdir())
        input_path = str(items[0]) if len(items) == 1 and items[0].is_dir() else str(extract_dir)
    elif len(files) == 1:
        # 情况 2：单文件 .txt/.md → 直接保存
        upload_path = UPLOAD_DIR / f"{task_id}_{files[0].filename}"
        with open(upload_path, "wb") as f:
            shutil.copyfileobj(files[0].file, f)
        input_path = str(upload_path)
    else:
        # 情况 3：多文件 → 合并为一个带章节标记的文本
        input_path = _merge_chapter_files(files, task_id)

    _tasks[task_id] = {
        "task_id": task_id,
        "status": "processing",
        "script_type": script_type,
        "mode": mode,
        "panel_mode": panel_mode,
        "api_key": effective_api_key,
        "ai_config": ai_config_obj.model_dump() if ai_config_obj else None,
        "episode_config": episode_config_obj.model_dump() if episode_config_obj else None,
        "input_path": str(input_path),
        "result_path": None,
        "error": None,
    }

    # 同步执行转换（适合本地单用户使用）
    try:
        script_doc = convert_novel(
            input_path=Path(input_path),
            script_type=script_type,
            mode=mode,
            panel_mode=panel_mode,
            api_key=effective_api_key,
            ai_config=ai_config_obj.model_dump() if ai_config_obj else None,
        )

        # 保存结果 YAML
        result_path = RESULTS_DIR / f"{task_id}_剧本.yaml"
        script_doc.save(result_path)

        root = script_doc.script

        # 构建集摘要列表
        episodes_summary = None
        if root.episodes:
            episodes_summary = [
                EpisodeSummary(
                    episode_id=ep.episode_id,
                    episode_number=ep.episode_number,
                    title=ep.title,
                    hook=ep.hook,
                    target_duration_seconds=ep.target_duration_seconds,
                    source_chapters=ep.source_chapters,
                    scenes=ep.scenes,
                    scene_count=len(ep.scenes),
                ).model_dump()
                for ep in root.episodes
            ]

        _tasks[task_id].update({
            "status": "completed",
            "result_path": str(result_path),
            "total_scenes": root.metadata.total_scenes,
            "total_beats": root.metadata.total_beats,
            "total_episodes": root.metadata.total_episodes,
            "estimated_duration_minutes": root.metadata.estimated_duration_minutes,
            "episodes": episodes_summary,
        })

        return ConvertResponse(
            task_id=task_id,
            status="completed",
            message="转换成功",
        )

    except Exception as e:
        _tasks[task_id].update({
            "status": "failed",
            "error": str(e),
        })
        return ConvertResponse(
            task_id=task_id,
            status="failed",
            message=str(e),
        )


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """查询任务状态和结果摘要"""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    t = _tasks[task_id]

    # 反序列化 episodes（存储时已转为 dict）
    episodes_list = None
    if t.get("episodes"):
        episodes_list = [EpisodeSummary(**ep) for ep in t["episodes"]]

    return TaskStatusResponse(
        task_id=task_id,
        status=t["status"],
        script_type=t["script_type"],
        mode=t["mode"],
        total_scenes=t.get("total_scenes"),
        total_beats=t.get("total_beats"),
        total_episodes=t.get("total_episodes"),
        estimated_duration_minutes=t.get("estimated_duration_minutes"),
        episodes=episodes_list,
        error=t.get("error"),
        download_url=f"/api/convert/{task_id}/download" if t["status"] == "completed" else None,
    )


@router.get("/{task_id}/download")
async def download_result(task_id: str):
    """下载生成的 YAML 文件"""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    t = _tasks[task_id]
    if t["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")

    result_path = Path(t["result_path"])
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="结果文件不存在")

    return FileResponse(
        path=result_path,
        filename=f"{task_id}_剧本.yaml",
        media_type="application/x-yaml",
    )
