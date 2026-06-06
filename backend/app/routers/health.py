from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api", tags=["health"])

# Demo novel path
_DEMO_PATH = Path(__file__).resolve().parent.parent.parent.parent / "examples" / "demo_novel_3chapters.md"


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "novel-to-script-backend"}


@router.get("/demo", response_class=PlainTextResponse)
async def get_demo_novel():
    """返回示例小说文本（3 章），供前端 Load Demo 按钮使用。"""
    if _DEMO_PATH.exists():
        return _DEMO_PATH.read_text(encoding="utf-8")
    return "# Demo not found"

