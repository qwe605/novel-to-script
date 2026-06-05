"""
AI 提供商管理路由：列表、连通性测试、模型发现。
"""

import time
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException

from app.core.config import PROVIDER_CONFIGS
from app.models.schemas import ProviderInfo, ProviderTestRequest, ProviderTestResponse

router = APIRouter(prefix="/api/providers", tags=["providers"])


# ========== 提供商信息 ==========


@router.get("", response_model=list[ProviderInfo])
async def list_providers():
    """返回所有支持的 AI 提供商及其默认配置"""
    return [
        ProviderInfo(
            key=key,
            name=cfg["name"],
            default_base_url=cfg["default_base_url"],
            default_model=cfg["default_model"],
            known_models=cfg["known_models"],
            api_type=cfg["api_type"],
        )
        for key, cfg in PROVIDER_CONFIGS.items()
    ]


# ========== 连通性测试 + 模型发现 ==========


@router.post("/test", response_model=ProviderTestResponse)
async def test_provider_connection(req: ProviderTestRequest):
    """
    测试 AI 提供商连通性，并尝试拉取可用模型列表。

    测试策略：
    - OpenAI-compatible: GET {base_url}/models → 验证 key 有效 + 获取模型列表
    - Anthropic:     POST {base_url}/v1/messages → 轻量请求验证 key
    """
    provider = req.provider
    if provider not in PROVIDER_CONFIGS:
        raise HTTPException(status_code=400, detail=f"未知提供商: {provider}")

    cfg = PROVIDER_CONFIGS[provider]
    base_url = (req.base_url or cfg["default_base_url"]).rstrip("/")
    api_key = req.api_key
    model = req.model or cfg["default_model"]
    api_type = cfg["api_type"]

    t0 = time.perf_counter()

    try:
        if api_type == "openai_compatible":
            result = await _test_openai_compatible(base_url, api_key, model)
        else:
            result = await _test_anthropic(base_url, api_key, model)

        latency = round((time.perf_counter() - t0) * 1000, 1)
        result["latency_ms"] = latency
        result["provider"] = provider

        return ProviderTestResponse(**result)

    except httpx.ConnectError:
        latency = round((time.perf_counter() - t0) * 1000, 1)
        return ProviderTestResponse(
            ok=False,
            provider=provider,
            model_used=model,
            message=f"无法连接到 {base_url} — 请检查 base_url 是否正确",
            latency_ms=latency,
        )
    except httpx.TimeoutException:
        latency = round((time.perf_counter() - t0) * 1000, 1)
        return ProviderTestResponse(
            ok=False,
            provider=provider,
            model_used=model,
            message=f"连接 {base_url} 超时 — 请检查网络或 base_url",
            latency_ms=latency,
        )
    except Exception as e:
        latency = round((time.perf_counter() - t0) * 1000, 1)
        return ProviderTestResponse(
            ok=False,
            provider=provider,
            model_used=model,
            message=str(e),
            latency_ms=latency,
        )


async def _test_openai_compatible(base_url: str, api_key: str, model: str) -> dict:
    """测试 OpenAI-compatible 接口：拉取模型列表 + 轻量聊天测试"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    available_models: Optional[list[dict]] = None

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. 尝试拉取模型列表（部分提供商支持）
        try:
            resp = await client.get(f"{base_url}/models", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                raw_models = data.get("data", data.get("models", []))
                available_models = [
                    {"id": m.get("id", m), "owned_by": m.get("owned_by", "")}
                    for m in raw_models
                ][:50]  # 限制数量
        except Exception:
            pass  # 模型列表拉取失败不影响连通性判断

        # 2. 轻量聊天请求验证 key 和模型
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            },
        )
        if resp.status_code in (200, 201):
            return {
                "ok": True,
                "model_used": model,
                "message": "连接成功 — API Key 有效",
                "available_models": available_models,
            }
        elif resp.status_code == 401:
            return {
                "ok": False,
                "model_used": model,
                "message": "API Key 无效 — 请检查 Key 是否正确",
                "available_models": available_models,
            }
        elif resp.status_code == 404:
            return {
                "ok": False,
                "model_used": model,
                "message": f"模型 '{model}' 不存在，但连接成功 — 请检查模型名称",
                "available_models": available_models,
            }
        else:
            body = resp.text[:200]
            return {
                "ok": False,
                "model_used": model,
                "message": f"HTTP {resp.status_code}: {body}",
                "available_models": available_models,
            }


async def _test_anthropic(base_url: str, api_key: str, model: str) -> dict:
    """测试 Anthropic 接口：发送轻量消息验证 key"""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"{base_url}/v1/messages",
            headers=headers,
            json={
                "model": model,
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "ping"}],
            },
        )
        if resp.status_code in (200, 201):
            return {
                "ok": True,
                "model_used": model,
                "message": "连接成功 — API Key 有效",
                "available_models": None,
            }
        elif resp.status_code == 401:
            return {
                "ok": False,
                "model_used": model,
                "message": "API Key 无效 — 请检查 Key 是否正确",
                "available_models": None,
            }
        else:
            body = resp.text[:200]
            return {
                "ok": False,
                "model_used": model,
                "message": f"HTTP {resp.status_code}: {body}",
                "available_models": None,
            }
