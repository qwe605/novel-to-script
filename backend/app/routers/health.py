import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api", tags=["health"])

# Demo novel — try disk path, fallback to bundled file
_DEMO_PATH = Path(__file__).resolve().parent.parent.parent.parent / "examples" / "demo_novel_3chapters.md"


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "novel-to-script-backend"}


@router.get("/demo", response_class=PlainTextResponse)
async def get_demo_novel():
    if _DEMO_PATH.exists():
        return _DEMO_PATH.read_text(encoding="utf-8")
    # Vercel 环境 — 从 api/ 同级目录查找
    alt = Path(__file__).resolve().parent.parent / "examples" / "demo_novel_3chapters.md"
    if alt.exists():
        return alt.read_text(encoding="utf-8")
    return "###1. 第一章\n\n请通过文件上传来体验转换功能。"

