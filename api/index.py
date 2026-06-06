"""
Vercel Serverless 入口 — 导入 FastAPI app 并导出为 ASGI handler。
2025 年 Vercel 原生支持 ASGI，无需 Mangum。
"""

import sys
from pathlib import Path

# 确保 backend/ 和 scripts/ 在 sys.path 中
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from backend.app.main import app  # noqa: E402
