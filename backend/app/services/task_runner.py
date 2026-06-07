"""
后台任务执行器。
使用线程池执行转换任务，通过 on_progress 回调实时更新进度。
"""

from __future__ import annotations

import traceback
from pathlib import Path

from app.services.task_store import store

# 简单的线程池（避免引入 celery 等重量级依赖）
_executor = None


def _get_executor():
    """延迟创建线程"""
    global _executor
    if _executor is None:
        import concurrent.futures
        _executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    return _executor


def run_conversion(
    task_id: str,
    *,
    input_path: Path,
    script_type: str,
    mode: str,
    panel_mode: str,
    title: str | None = None,
    api_key: str | None = None,
    ai_config: dict | None = None,
    episode_config: dict | None = None,
    results_dir: Path | None = None,
) -> None:
    """
    在后台线程中执行转换，通过 store.update() 持续更新进度和结果。
    前端通过 GET /api/convert/{task_id} 轮询 progress 字段。
    """

    def _run():
        def on_progress(phase: str, pct: float):
            try:
                store.update(task_id, {"progress": pct, "progress_message": phase})
            except KeyError:
                pass

        try:
            on_progress("初始化", 0.0)

            from app.services.converter import run_pipeline

            timing_log: dict[str, float] = {}
            script_doc = run_pipeline(
                input_path=input_path,
                script_type=script_type,
                mode=mode,
                panel_mode=panel_mode,
                title=title,
                api_key=api_key,
                ai_config=ai_config,
                episode_config=episode_config,
                on_progress=on_progress,
                timing_log=timing_log,
            )

            # 保存 YAML
            result_path = results_dir / f"{task_id}_剧本.yaml"
            script_doc.save(result_path)

            root = script_doc.script

            # 构建集摘要
            episodes_summary = None
            if root.episodes:
                from app.models.schemas import EpisodeSummary
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

            store.update(task_id, {
                "status": "completed", "progress": 1.0,
                "progress_message": "转换完成",
                "result_path": str(result_path),
                "title": root.title,
                "characters": [c.model_dump() for c in root.characters],
                "timing": timing_log,
                "total_scenes": root.metadata.total_scenes,
                "total_beats": root.metadata.total_beats,
                "total_episodes": root.metadata.total_episodes,
                "estimated_duration_minutes": root.metadata.estimated_duration_minutes,
                "episodes": episodes_summary,
            })

        except Exception as e:
            tb = traceback.format_exc()
            import sys
            # 打印到 stderr 方便调试
            print(f"\n[ERROR] task {task_id} failed:\n{tb}", file=sys.stderr)
            # 取最后 3 行作为简要信息
            tb_lines = tb.strip().split("\n")
            short_msg = "\n".join(tb_lines[-4:]) if len(tb_lines) > 4 else tb
            store.update(task_id, {
                "status": "failed", "progress": 0,
                "progress_message": f"转换失败: {e}",
                "error": f"{e}\n\n详细堆栈:\n{short_msg}",
            })

    _get_executor().submit(_run)
