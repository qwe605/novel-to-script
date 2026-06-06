from pydantic import BaseModel, Field
from typing import Optional


# ========== AI 配置 ==========

class AIConfig(BaseModel):
    """AI 模型配置"""
    provider: str = "deepseek"   # anthropic | openai | deepseek | openrouter | custom
    api_key: Optional[str] = None
    model: str = "deepseek-chat"
    base_url: Optional[str] = None  # 覆盖默认 base_url
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=8192, ge=100, le=200000)
    system_prompt: Optional[str] = None
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)


# ========== 分集配置 ==========

class EpisodeConfig(BaseModel):
    """分集设置"""
    enabled: bool = True
    target_episodes: Optional[int] = Field(default=None, ge=1, le=500)
    min_duration_seconds: int = Field(default=180, ge=60, le=600)
    max_duration_seconds: int = Field(default=300, ge=60, le=600)
    hook_style: str = "cliffhanger"
    auto_split: bool = True
    title_template: str = "第{n}集{pause}{subtitle}"


# ========== 提供商测试 ==========

class ProviderTestRequest(BaseModel):
    """测试 AI 提供商连通性"""
    provider: str = "deepseek"
    api_key: str
    base_url: Optional[str] = None
    model: Optional[str] = None  # 不传则用 provider 默认模型


class ProviderTestResponse(BaseModel):
    """连通性测试结果"""
    ok: bool
    provider: str
    model_used: str
    message: str
    latency_ms: Optional[float] = None
    available_models: Optional[list[dict]] = None  # [{id, owned_by}]


class ProviderInfo(BaseModel):
    """提供商静态信息"""
    key: str
    name: str
    default_base_url: str
    default_model: str
    known_models: list[str]
    api_type: str  # anthropic | openai_compatible


# ========== 转换请求/响应 ==========

class ConvertRequest(BaseModel):
    script_type: str = "manju"
    mode: str = "rule"
    panel_mode: str = "simple"
    ai_config: Optional[AIConfig] = None
    episode_config: Optional[EpisodeConfig] = None

    # 向后兼容
    api_key: Optional[str] = None


class ConvertResponse(BaseModel):
    task_id: str
    status: str
    message: str


class EpisodeSummary(BaseModel):
    """集摘要（供前端展示）"""
    episode_id: str
    episode_number: int
    title: Optional[str] = None
    hook: Optional[str] = None
    target_duration_seconds: int = 240
    source_chapters: Optional[list[int]] = None
    scenes: list[str] = []
    scene_count: int = 0


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    script_type: str
    mode: str
    title: Optional[str] = None            # 剧本标题
    characters: Optional[list[dict]] = None # 角色列表（供封面生成等场景使用）
    progress: Optional[float] = None       # 0.0 – 1.0
    progress_message: Optional[str] = None  # 当前阶段描述
    timing: Optional[dict[str, float]] = None  # 各阶段耗时（秒）：{"加载":0.1,"场景检测":12.3,...}
    total_scenes: Optional[int] = None
    total_beats: Optional[int] = None
    total_episodes: Optional[int] = None
    estimated_duration_minutes: Optional[float] = None
    episodes: Optional[list[EpisodeSummary]] = None
    error: Optional[str] = None
    download_url: Optional[str] = None
