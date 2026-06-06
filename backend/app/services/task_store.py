"""
任务持久化存储。
在内存 dict 之上增加 JSON 文件持久层，服务重启后任务不丢失。

设计：
- 每个任务存储为 {tasks_dir}/{task_id}.json
- 读写以内存为主，写操作同步落盘
- 启动时从磁盘恢复所有任务到内存
- 不持久化 file-like 字段（如 UploadFile、FileResponse）
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.core.config import BASE_DIR

TASKS_DIR = BASE_DIR / "tasks"
TASKS_DIR.mkdir(exist_ok=True)


class TaskStore:
    """带 JSON 持久化的任务存储"""

    def __init__(self, tasks_dir: Path | None = None):
        self._dir = tasks_dir or TASKS_DIR
        self._dir.mkdir(exist_ok=True)
        self._cache: dict[str, dict] = {}

    # ---- public API ----

    def create(self, task_id: str, data: dict) -> None:
        """创建新任务（覆盖写入）"""
        data.setdefault("created_at", time.time())
        self._cache[task_id] = data
        self._save(task_id)

    def get(self, task_id: str) -> dict | None:
        """获取任务数据"""
        return self._cache.get(task_id)

    def update(self, task_id: str, updates: dict) -> None:
        """增量更新任务字段"""
        if task_id not in self._cache:
            raise KeyError(f"任务不存在: {task_id}")
        self._cache[task_id].update(updates)
        self._save(task_id)

    def exists(self, task_id: str) -> bool:
        return task_id in self._cache

    def delete(self, task_id: str) -> None:
        """删除任务（内存 + 磁盘）"""
        self._cache.pop(task_id, None)
        fpath = self._file_path(task_id)
        try:
            fpath.unlink(missing_ok=True)
        except OSError:
            pass

    def load_all(self) -> list[str]:
        """
        从磁盘恢复所有任务到内存。
        应在服务启动时调用一次。
        返回恢复的任务 ID 列表。
        """
        recovered: list[str] = []
        for fpath in sorted(self._dir.glob("*.json")):
            tid = fpath.stem
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                # 跳过已完成的旧任务（可选策略：也可全部恢复）
                self._cache[tid] = data
                recovered.append(tid)
            except (json.JSONDecodeError, OSError):
                # 损坏的文件跳过
                pass
        return recovered

    def cleanup_expired(self, ttl_seconds: float = 86400) -> int:
        """
        清理超过 TTL 的已完成/失败任务。
        返回清理数量。
        """
        now = time.time()
        expired_ids: list[str] = []
        for tid, data in self._cache.items():
            age = now - data.get("created_at", now)
            if age > ttl_seconds and data.get("status") in ("completed", "failed"):
                expired_ids.append(tid)
        for tid in expired_ids:
            self.delete(tid)
        return len(expired_ids)

    # ---- internal ----

    def _file_path(self, task_id: str) -> Path:
        # 防止路径穿越
        safe_id = task_id.replace("/", "_").replace("\\", "_")
        return self._dir / f"{safe_id}.json"

    def _save(self, task_id: str) -> None:
        """将单个任务序列化到磁盘"""
        data = self._cache.get(task_id)
        if data is None:
            return
        # 只持久化 JSON-safe 字段
        serializable = {}
        for k, v in data.items():
            if isinstance(v, (str, int, float, bool, list, dict, type(None))):
                serializable[k] = v
            elif isinstance(v, Path):
                serializable[k] = str(v)
            # 跳过不可序列化的字段（如 UploadFile 对象）
        try:
            self._file_path(task_id).write_text(
                json.dumps(serializable, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass  # 磁盘写入失败不影响内存操作


# 单例
store = TaskStore()
