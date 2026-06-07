"""
AI 辅助编辑 API：对场景/节拍提供 AI 辅助增强修改建议。
POST /api/assist
"""

import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/assist", tags=["assist"])


class AssistRequest(BaseModel):
    context_type: str = Field(..., description="scene | beat")
    context_data: dict = Field(..., description="当前场景/节拍的完整数据")
    script_context: dict = Field(default_factory=dict, description="全局上下文：title, characters 等")
    message: str = Field(..., description="用户的编辑需求")
    history: list[dict] = Field(default_factory=list, description="对话历史 [{role, content}]")
    provider: str = Field("deepseek", description="AI 提供商")
    api_key: str | None = Field(None)
    model: str | None = Field(None)
    base_url: str | None = Field(None)


class AssistResponse(BaseModel):
    reply: str


PROVIDER_DEFAULTS = {
    "anthropic": {"base_url": "https://api.anthropic.com", "default_model": "claude-sonnet-4-6", "api_type": "anthropic"},
    "openai": {"base_url": "https://api.openai.com/v1", "default_model": "gpt-4o", "api_type": "openai_compatible"},
    "deepseek": {"base_url": "https://api.deepseek.com", "default_model": "deepseek-chat", "api_type": "openai_compatible"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "default_model": "openai/gpt-4o", "api_type": "openai_compatible"},
    "custom": {"base_url": "http://localhost:11434/v1", "default_model": "llama3", "api_type": "openai_compatible"},
}


SCENE_SYSTEM_PROMPT = """你是一位专业的网文漫剧编剧/导演，正在帮助用户优化剧本中的场景。

## 你可以帮助用户：
1. **地点优化**：让 location 更具体、更有视觉感（细化到子空间，如"别墅-主卧"而非"房间"）
2. **时间调整**：建议更合适的 DAY/NIGHT/DAWN/DUSK/LATER/CONTINUOUS
3. **情绪改写**：优化 mood 字段，用"起点→终点"格式（如"平静→警觉"）
4. **类型判断**：建议 dialogue_heavy/action/montage/transition/static
5. **场景拆分/合并建议**：判断当前场景是否过长或过短

## 铁律
- 只写能被摄影机/画面捕捉的内容
- 不写心理描写（"他感到""她意识到"等）
- 对白要口语化，像真人说话
- 地点要可拍摄/可画出

## 回复格式
直接给出具体建议，不要客套话。如果用户要求改写某个字段，给出改写后的值并简要说明理由。
如果用户要求整体优化，列出 2-4 条具体改进建议。"""

BEAT_SYSTEM_PROMPT = """你是一位专业的网文漫剧编剧/导演，正在帮助用户优化剧本中的节拍（Beat）。

## 节拍类型参考
- action: 角色动作、环境变化、视觉呈现
- dialogue: 角色说出的台词
- narration: 旁白/画外音
- vos: 角色内心独白（画外音）
- sfx: 音效提示
- music: 音乐提示
- transition: 场景转换

## 你可以帮助用户：
1. **动作改写**：让动作更有画面感、更有冲击力
2. **对白优化**：让台词更口语化、更有潜台词
3. **类型调整**：建议更合适的 beat 类型
4. **角色归因**：帮助判断这句话是谁说的
5. **parenthetical 优化**：建议合适的语气提示（≤10字）
6. **对白去 AI 味**：去掉过于书面化、比喻句、解释性台词

## 铁律
- 动作反应单元：一个动作 + 一个反应 = 最小叙事单元
- 对白要口语化，短促自然
- 不写心理描写
- 用动作替代解释（动作即潜台词）
- parenthetical 只能标注语气或极简动作，不能解释心理

## 回复格式
直接给出具体建议。如果用户要求改写某段内容，给出改写后的版本。
如果用户要求优化整体，列出 2-3 条改进建议。"""


def _build_context_desc(req: AssistRequest) -> str:
    """构建上下文描述文本"""
    parts = []
    ctx = req.context_data
    script = req.script_context

    if script.get("title"):
        parts.append(f"剧本：{script['title']}")

    if req.context_type == "scene":
        loc = ctx.get("heading", {}).get("location", "")
        t = ctx.get("heading", {}).get("time", "")
        mood = ctx.get("mood", "")
        stype = ctx.get("type", "")
        chs = ctx.get("characters", [])
        parts.append(f"地点：{loc}")
        parts.append(f"时间：{t}")
        if mood:
            parts.append(f"情绪：{mood}")
        if stype:
            parts.append(f"类型：{stype}")
        if chs:
            parts.append(f"角色：{', '.join(chs)}")
        # 附上 beats 摘要
        beats = ctx.get("beats", [])
        if beats:
            parts.append(f"包含 {len(beats)} 个节拍")
            for b in beats[:5]:
                ch = b.get("character", "—")
                ct = (b.get("content", "") or "")[:40]
                parts.append(f"  [{b.get('type','?')}] {ch}: {ct}")

    elif req.context_type == "beat":
        bt = ctx.get("type", "action")
        bc = ctx.get("content", "")
        bch = ctx.get("character", "")
        bp = ctx.get("parenthetical", "")
        parts.append(f"类型：{bt}")
        parts.append(f"内容：{bc}")
        if bch:
            parts.append(f"角色：{bch}")
        if bp:
            parts.append(f"语气：{bp}")

    return "\n".join(parts)


def _call_ai(req: AssistRequest, system_prompt: str) -> str:
    """调用 AI 提供商"""
    provider = req.provider.lower()
    pcfg = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["deepseek"])
    api_type = pcfg["api_type"]
    base_url = (req.base_url or pcfg["base_url"]).rstrip("/")
    model = req.model or pcfg["default_model"]
    api_key = req.api_key

    if not api_key:
        import os
        api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("DEFAULT_AI_API_KEY")

    if not api_key:
        raise HTTPException(status_code=400, detail="需要 API Key：请在 AI 设置中配置 API Key")

    context_desc = _build_context_desc(req)

    # 构建消息
    messages = [{"role": "system", "content": system_prompt}]

    # 附加对话历史
    for h in (req.history or [])[-10:]:
        role = h.get("role", "user")
        content = h.get("content", "")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": content})

    # 当前用户消息（带上下文）
    user_msg = f"当前编辑上下文：\n```\n{context_desc}\n```\n\n用户需求：{req.message}"
    messages.append({"role": "user", "content": user_msg})

    if api_type == "anthropic":
        try:
            import anthropic
        except ImportError:
            raise HTTPException(status_code=500, detail="需要安装 anthropic 库")
        client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
        system = messages[0]["content"]
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            temperature=0.7,
            system=system,
            messages=[{"role": m["role"], "content": m["content"]} for m in messages[1:]],
        )
        return response.content[0].text
    else:
        try:
            from openai import OpenAI
        except ImportError:
            raise HTTPException(status_code=500, detail="需要安装 openai 库")
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            max_tokens=2048,
            temperature=0.7,
            messages=messages,
        )
        return response.choices[0].message.content or ""


@router.post("", response_model=AssistResponse)
async def ai_assist(req: AssistRequest):
    """AI 辅助编辑：根据场景/节拍上下文和用户需求，返回具体建议"""
    if req.context_type not in ("scene", "beat"):
        raise HTTPException(status_code=400, detail="context_type 必须是 scene 或 beat")

    system_prompt = SCENE_SYSTEM_PROMPT if req.context_type == "scene" else BEAT_SYSTEM_PROMPT

    try:
        reply = _call_ai(req, system_prompt)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 调用失败: {e}")

    return AssistResponse(reply=reply)
