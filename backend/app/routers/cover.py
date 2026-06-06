"""
封面图生成路由。
根据剧本 metadata + episode/character 信息生成漫画风格封面提示词。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/cover", tags=["cover"])


class CoverRequest(BaseModel):
    title: str = Field(..., description="剧本标题")
    script_type: str = Field(default="manju")
    hook: str | None = Field(None, description="集末钩子/剧情亮点")
    characters: list[dict] | None = Field(None, description="角色列表 [{name, archetype, visual_tags}]")
    mood: str | None = Field(None, description="情绪基调")
    episode_title: str | None = Field(None, description="集标题")


class CoverResponse(BaseModel):
    prompt_cn: str = Field(..., description="中文封面提示词")
    prompt_en: str = Field(..., description="英文封面提示词（供 AI 绘图 API 使用）")
    style: str = Field(..., description="推荐风格")
    aspect_ratio: str = Field(default="9:16", description="宽高比")


# ===== 风格预设 =====

_STYLES = {
    "manju": {
        "name": "漫画封面风格",
        "base": "high-quality Chinese manhua cover art, dynamic composition, dramatic lighting, rich color palette, clean linework with soft shading",
        "aspect": "9:16",
    },
    "screenplay": {
        "name": "电影海报风格",
        "base": "cinematic movie poster, film grain, dramatic composition, professional Hollywood style, high contrast",
        "aspect": "2:3",
    },
    "audio_drama": {
        "name": "有声书封面",
        "base": "audiobook cover art, atmospheric and evocative, minimalist design with emotional resonance, soft focus",
        "aspect": "1:1",
    },
    "stage_play": {
        "name": "舞台剧海报",
        "base": "theatre playbill poster, bold typography-ready composition, theatrical spotlight, dramatic shadows",
        "aspect": "2:3",
    },
}

# ===== 角色外貌模板 =====

_VISUAL_TAG_MAP: dict[str, str] = {
    "黑长直": "long straight black hair",
    "短发": "short hair",
    "异色瞳": "heterochromia eyes",
    "眼镜": "wearing glasses",
    "白衣": "wearing white clothing",
    "黑衣": "wearing black clothing",
    "校服": "school uniform",
    "古装": "traditional Chinese hanfu clothing",
    "披风": "wearing a cape",
    "冷酷": "cold and sharp gaze",
    "温柔": "gentle warm expression",
    "病弱": "pale and frail appearance",
}


def _build_character_desc(characters: list[dict] | None) -> str:
    if not characters:
        return ""
    parts = []
    for c in characters[:3]:  # 最多 3 个角色
        name = c.get("name", "").split("：")[-1].split("（")[0].strip()
        desc = c.get("description", "")
        tags = c.get("visual_tags") or []
        archetype = c.get("archetype", "")
        tag_desc = ", ".join(_VISUAL_TAG_MAP.get(t, t) for t in tags if t)
        if name:
            line = name
            if tag_desc:
                line += f" ({tag_desc})"
            if archetype:
                line += f" — {archetype}"
            parts.append(line)
    return "；".join(parts) if parts else ""


def _build_prompt_en(title: str, hook: str | None, char_desc: str, mood: str | None, style_base: str) -> str:
    """构建英文 AI 绘图提示词"""
    elements = [style_base]
    if title:
        elements.append(f'centered title "{title}"')
    if char_desc:
        elements.append(f"featuring: {char_desc}")
    if hook:
        elements.append(f"scene: {hook}")
    if mood:
        elements.append(f"mood: {mood}")
    elements.append("professional illustration, trending on ArtStation, pixiv, 8k detailed")
    return ", ".join(elements)


def _build_prompt_cn(title: str, hook: str | None, char_desc: str, mood: str | None, style_name: str) -> str:
    """构建中文提示词（供手动参考）"""
    parts = [f"【风格】{style_name}"]
    if title:
        parts.append(f"【标题】《{title}》")
    if hook:
        parts.append(f"【画面】{hook}")
    if char_desc:
        parts.append(f"【角色】{char_desc}")
    if mood:
        parts.append(f"【情绪】{mood}")
    parts.append("【要求】高质量插画，角色居中，动态构图，丰富色彩，清晰线条")
    return "\n".join(parts)


@router.post("", response_model=CoverResponse)
async def generate_cover(req: CoverRequest):
    """根据剧本信息生成封面图提示词"""
    style = _STYLES.get(req.script_type, _STYLES["manju"])

    char_desc = _build_character_desc(req.characters)
    hook_text = req.hook or req.episode_title or ""

    prompt_en = _build_prompt_en(req.title, hook_text, char_desc, req.mood, style["base"])
    prompt_cn = _build_prompt_cn(req.title, hook_text, char_desc, req.mood, style["name"])

    return CoverResponse(
        prompt_cn=prompt_cn,
        prompt_en=prompt_en,
        style=style["name"],
        aspect_ratio=style["aspect"],
    )
