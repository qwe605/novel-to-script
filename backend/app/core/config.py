import os
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()

IS_VERCEL = bool(os.getenv("VERCEL"))

if IS_VERCEL:
    BASE_DIR = Path("/tmp")
else:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

UPLOAD_DIR = BASE_DIR / "uploads"
RESULTS_DIR = BASE_DIR / "results"
UPLOAD_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173").split(",")

# ========== AI 默认配置（来自 .env）==========

# 默认提供商
DEFAULT_AI_PROVIDER = os.getenv("DEFAULT_AI_PROVIDER", "deepseek")

# 默认 API Key — 仅在规则模式或用户未提供 key 时使用
DEFAULT_AI_API_KEY = os.getenv("DEFAULT_AI_API_KEY", "")

# 默认模型
DEFAULT_AI_MODEL = os.getenv("DEFAULT_AI_MODEL", "deepseek-chat")

# 默认 base URL（可选，留空则使用各 provider 内置默认值）
DEFAULT_AI_BASE_URL = os.getenv("DEFAULT_AI_BASE_URL", "")

# =============================================================================
# 提供商内置配置（CANONICAL SOURCE）
# 此处是 AI provider 配置的唯一事实来源。
# scripts/scene_detector.py 的 PROVIDER_DEFAULTS 和前端 fallback 必须与此处一致。
# 新增/修改 provider 时只需改此处；前端启动时自动从 /api/providers 拉取。
# =============================================================================

PROVIDER_CONFIGS: dict[str, dict] = {
    "anthropic": {
        "name": "Anthropic",
        "default_base_url": "https://api.anthropic.com",
        "default_model": "claude-sonnet-4-6",
        "known_models": [
            "claude-sonnet-4-6",
            "claude-opus-4-8",
            "claude-opus-4-7",
            "claude-haiku-4-5",
            "claude-sonnet-4-5",
        ],
        "api_type": "anthropic",  # 使用原生 Anthropic SDK
    },
    "openai": {
        "name": "OpenAI",
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o",
        "known_models": [
            "gpt-4o",
            "gpt-4.1",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "o4-mini",
        ],
        "api_type": "openai_compatible",
    },
    "deepseek": {
        "name": "DeepSeek",
        "default_base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "known_models": [
            "deepseek-chat",
            "deepseek-reasoner",
        ],
        "api_type": "openai_compatible",
    },
    "openrouter": {
        "name": "OpenRouter",
        "default_base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o",
        "known_models": [
            "openai/gpt-4o",
            "anthropic/claude-sonnet-4-6",
            "anthropic/claude-opus-4-8",
            "google/gemini-2.5-pro",
            "meta-llama/llama-4-maverick",
        ],
        "api_type": "openai_compatible",
    },
    "custom": {
        "name": "自定义",
        "default_base_url": "http://localhost:11434/v1",
        "default_model": "llama3",
        "known_models": [],
        "api_type": "openai_compatible",
    },
}
