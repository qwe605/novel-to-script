"""
FastAPI 入口
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import ALLOWED_ORIGINS
from app.routers import convert, cover, health, providers

app = FastAPI(
    title="Novel-to-Script API",
    description="AI 辅助小说转剧本工具的后端 API",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(convert.router)
app.include_router(health.router)
app.include_router(providers.router)
app.include_router(cover.router)


@app.get("/")
async def root():
    return {"message": "Novel-to-Script API is running", "docs": "/docs"}
