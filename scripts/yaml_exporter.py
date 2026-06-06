"""
YAML 输出与校验模块
定义通用剧本 Schema 的 Pydantic v2 模型，提供序列化、反序列化和校验能力。
核心服务场景：网文漫剧（动态漫画/有声漫画），同时兼容影视剧本、广播剧、舞台剧。
"""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# 枚举类型约束
# =============================================================================

ScriptType = Literal["screenplay", "audio_drama", "stage_play", "manju"]
IntExt = Literal["INT.", "EXT.", "INT./EXT."]
SceneType = Literal["dialogue_heavy", "action", "montage", "transition", "static"]
BeatType = Literal["action", "dialogue", "transition", "sfx", "music", "narration", "vos"]

# 漫剧视觉特效枚举 —— 覆盖网文漫剧常见视觉手法
ManjuEffect = Literal[
    "FLASH_WHITE",      # 闪白
    "FLASH_BLACK",      # 闪黑
    "ZOOM_IN_EYE",      # 瞳孔放大
    "MEMORY_FILTER",    # 回忆滤镜（黑白/柔光/老照片）
    "SLOW_MOTION",      # 慢动作
    "SHAKE",            # 画面震动
    "SPLIT_SCREEN",     # 分屏
    "MONTAGE",          # 蒙太奇快切
    "DANMAKU",          # 弹幕式字幕
    "SPEED_LINE",       # 速度线
    "FOCUS_BLUR",       # 聚焦模糊（背景虚化）
    "SILHOUETTE",       # 剪影
    "RIPPLE",           # 水波纹转场
    "PARTICLE",         # 粒子特效（花瓣/雪花/光点）
    "COLOR_INVERT",     # 颜色反相
]

SubtitleStyle = Literal[
    "NORMAL",       # 普通字幕
    "DANMAKU",      # 弹幕式（从右向左滚动）
    "BUBBLE",       # 漫画气泡式
    "NARRATION",    # 旁白条（顶部/底部静态）
    "PHONE",        # 手机聊天界面式
    "THOUGHT",      # 内心独白（云状框/斜体）
]


# =============================================================================
# 扩展字段模型
# =============================================================================

class ScreenplayExtensions(BaseModel):
    """影视剧本专属扩展字段"""
    shot: Optional[str] = Field(None, description="景别，如 CLOSE-UP / WIDE / POV")
    camera_move: Optional[str] = Field(None, description="镜头运动，如 PAN / DOLLY / HANDHELD")
    transition: Optional[str] = Field(None, description="转场方式，如 CUT TO / FADE IN / DISSOLVE TO")


class AudioDramaExtensions(BaseModel):
    """广播剧/有声书专属扩展字段"""
    sfx: Optional[list[str]] = Field(None, description="音效列表")
    bgm: Optional[str] = Field(None, description="背景音乐提示")
    narration_tone: Optional[str] = Field(None, description="旁白语气")
    pan: Optional[str] = Field(None, description="声像定位，如 L→R / 远→近")


class StagePlayExtensions(BaseModel):
    """舞台剧专属扩展字段"""
    stage_direction: Optional[str] = Field(None, description="舞台走位/动作指示")
    lighting: Optional[str] = Field(None, description="灯光提示")
    set_change: Optional[str] = Field(None, description="换景说明")


class ManjuExtensions(BaseModel):
    """
    网文漫剧（动态漫画/有声漫画）专属扩展字段。
    漫剧是本服的核心场景，融合了画面分镜、配音、音效、字幕。
    """
    # ---- 画面层（两种粒度共用） ----
    shot: Optional[str] = Field(None, description="景别：CLOSE-UP / MEDIUM / WIDE / POV / EXTREME_CLOSE-UP")
    frame_description: Optional[str] = Field(None, description="【详细模式】格内画面描述，供画师参考")
    dialogue_bubble: Optional[str] = Field(None, description="【详细模式】台词气泡位置：左上/右上/左下/右下/中央")
    sfx_visual: Optional[list[str]] = Field(None, description="【详细模式】视觉拟声词，如['砰','咔嚓']")

    # ---- 特效与转场 ----
    transition: Optional[str] = Field(None, description="转场方式")
    visual_effect: Optional[ManjuEffect] = Field(None, description="视觉特效枚举")
    effect_note: Optional[str] = Field(None, description="特效补充说明（如'回忆滤镜：泛黄老照片质感'）")

    # ---- 声音层 ----
    bgm: Optional[str] = Field(None, description="背景音乐提示")
    sfx: Optional[list[str]] = Field(None, description="音效列表")
    voice_direction: Optional[str] = Field(None, description="配音指导：语气、语速、情绪")

    # ---- 字幕层 ----
    subtitle_style: Optional[SubtitleStyle] = Field(None, description="字幕样式枚举")
    subtitle_note: Optional[str] = Field(None, description="字幕补充说明（如'红色加大字号'）")

    # ---- 时长 ----
    duration_frames: Optional[int] = Field(None, ge=1, description="持续帧数（24fps或30fps项目）")
    duration_seconds: Optional[float] = Field(None, ge=0, description="持续秒数（优先使用）")


class BeatExtensions(BaseModel):
    """Beat 级别的扩展字段容器"""
    screenplay: Optional[ScreenplayExtensions] = None
    audio_drama: Optional[AudioDramaExtensions] = None
    stage_play: Optional[StagePlayExtensions] = None
    manju: Optional[ManjuExtensions] = None


# =============================================================================
# 核心模型
# =============================================================================

class Metadata(BaseModel):
    """剧本全局元数据"""
    total_scenes: int = Field(..., ge=0, description="场景总数")
    total_beats: int = Field(..., ge=0, description="节拍总数")
    total_episodes: Optional[int] = Field(None, ge=0, description="总集数（漫剧必填）")
    estimated_duration_minutes: Optional[float] = Field(None, ge=0, description="预估总时长（分钟）")
    adapted_by: Optional[str] = Field(None, description="改编者")
    adaptation_notes: Optional[str] = Field(None, description="改编说明")


class Character(BaseModel):
    """角色定义"""
    id: str = Field(..., description="角色唯一标识（英文蛇形命名）")
    name: str = Field(..., description="角色名（中文）")
    aliases: Optional[list[str]] = Field(None, description="别名/昵称列表")
    description: Optional[str] = Field(None, description="角色简述")
    voice_tags: Optional[list[str]] = Field(None, description="声音/语言风格标签")
    archetype: Optional[str] = Field(None, description="角色原型")
    # 漫剧常用：角色立绘/表情差分提示
    visual_tags: Optional[list[str]] = Field(None, description="【漫剧】视觉特征标签，如['黑长直','异色瞳','常穿校服']")


class Sequence(BaseModel):
    """序列/幕定义（戏剧结构层）"""
    id: str = Field(..., description="序列唯一标识")
    name: str = Field(..., description="序列名称")
    description: Optional[str] = Field(None, description="序列内容简述")
    scenes: list[str] = Field(..., description="属于该序列的 Scene ID 列表")


class Episode(BaseModel):
    """
    集定义（漫剧核心组织单元）。
    每集 3-5 分钟，有独立悬念钩子，可独立传播。
    """
    episode_id: str = Field(..., description="集唯一标识，如 ep_01")
    episode_number: int = Field(..., ge=1, description="集序号")
    title: Optional[str] = Field(None, description="集标题")
    hook: Optional[str] = Field(None, description="本集悬念钩子/卡点（吸引观众追下一集）")
    target_duration_seconds: int = Field(240, ge=60, le=600, description="目标时长（秒），默认240秒=4分钟")
    source_chapters: Optional[list[int]] = Field(None, description="来源小说章节编号")
    scenes: list[str] = Field(..., description="属于该集的 Scene ID 列表")
    # 漫剧后期元数据
    cover_prompt: Optional[str] = Field(None, description="【漫剧】封面图提示词/参考")
    opening_sfx: Optional[str] = Field(None, description="【漫剧】片头标志性音效/音乐")


class SceneHeading(BaseModel):
    """场景标题（标准影视格式）"""
    int_ext: IntExt = Field(..., description="内景/外景")
    location: str = Field(..., description="地点")
    time: str = Field(..., description="时间")


class Beat(BaseModel):
    """场景内的最小叙事单元（漫剧中也对应一格/一镜）"""
    beat_id: str = Field(..., description="节拍唯一标识")
    type: BeatType = Field(..., description="节拍类型")
    character: Optional[str] = Field(None, description="关联角色 ID")
    content: str = Field(..., description="内容（动作/对白/音效等）")
    parenthetical: Optional[str] = Field(None, description="括号提示（语气/动作）")
    extensions: Optional[BeatExtensions] = None


class Scene(BaseModel):
    """场景定义（时空统一的叙事单位）"""
    scene_id: str = Field(..., description="场景唯一标识")
    sequence_id: str = Field(..., description="所属序列 ID")
    heading: SceneHeading = Field(..., description="场景标题")
    source_chapters: Optional[list[int]] = Field(None, description="来源小说章节编号")
    estimated_duration_seconds: Optional[int] = Field(None, ge=0, description="预估时长（秒）")
    type: Optional[SceneType] = Field(None, description="场景类型")
    mood: Optional[str] = Field(None, description="场景情绪")
    beats: list[Beat] = Field(..., description="节拍列表")


class ScriptRoot(BaseModel):
    """剧本根对象"""
    version: Literal["1.0"] = Field("1.0", description="Schema 版本")
    script_type: ScriptType = Field(..., description="剧本类型")
    title: str = Field(..., description="剧本标题")
    source: Optional[str] = Field(None, description="来源小说")
    metadata: Metadata = Field(..., description="全局元数据")
    characters: list[Character] = Field(..., description="角色列表")
    sequences: list[Sequence] = Field(..., description="序列/幕列表")
    episodes: Optional[list[Episode]] = Field(None, description="【漫剧】集列表，按集组织场景")
    scenes: list[Scene] = Field(..., description="场景列表")


class ScriptDocument(BaseModel):
    """顶层文档包装器"""
    script: ScriptRoot = Field(..., description="剧本根对象")

    def to_yaml(self, allow_unicode: bool = True) -> str:
        """序列化为 YAML 字符串"""
        data = self.model_dump(mode="json", exclude_none=True)
        return yaml.dump(
            data,
            allow_unicode=allow_unicode,
            sort_keys=False,
            default_flow_style=False,
            width=120,
        )

    def save(self, path: Path | str) -> None:
        """保存到文件"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_yaml(), encoding="utf-8")

    @classmethod
    def from_yaml(cls, yaml_text: str) -> "ScriptDocument":
        """从 YAML 字符串反序列化"""
        data = yaml.safe_load(yaml_text)
        return cls.model_validate(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "ScriptDocument":
        """从文件加载并校验"""
        path = Path(path)
        return cls.from_yaml(path.read_text(encoding="utf-8"))

    def validate_consistency(self) -> list[str]:
        """
        执行跨字段一致性检查，返回错误信息列表。
        空列表表示全部通过。
        """
        errors: list[str] = []
        root = self.script

        # 1. scene_id 唯一性
        scene_ids = [s.scene_id for s in root.scenes]
        if len(scene_ids) != len(set(scene_ids)):
            dup = {sid for sid in scene_ids if scene_ids.count(sid) > 1}
            errors.append(f"场景 ID 重复: {dup}")

        # 2. beat_id 唯一性
        beat_ids = [b.beat_id for s in root.scenes for b in s.beats]
        if len(beat_ids) != len(set(beat_ids)):
            dup = {bid for bid in beat_ids if beat_ids.count(bid) > 1}
            errors.append(f"节拍 ID 重复: {dup}")

        # 3. sequence_id 有效性
        valid_seq_ids = {sq.id for sq in root.sequences}
        for sc in root.scenes:
            if sc.sequence_id not in valid_seq_ids:
                errors.append(f"场景 '{sc.scene_id}' 引用了不存在的序列 '{sc.sequence_id}'")

        # 4. sequence.scenes 引用有效性
        valid_scene_ids = set(scene_ids)
        for sq in root.sequences:
            for sid in sq.scenes:
                if sid not in valid_scene_ids:
                    errors.append(f"序列 '{sq.id}' 引用了不存在的场景 '{sid}'")

        # 5. beat.character 有效性
        valid_char_ids = {c.id for c in root.characters}
        for sc in root.scenes:
            for b in sc.beats:
                if b.character and b.character not in valid_char_ids:
                    errors.append(
                        f"节拍 '{b.beat_id}' (场景 '{sc.scene_id}') 引用了不存在的角色 '{b.character}'"
                    )

        # 6. Episode 相关校验（漫剧）
        if root.episodes:
            # episode_id 唯一性
            ep_ids = [e.episode_id for e in root.episodes]
            if len(ep_ids) != len(set(ep_ids)):
                dup = {eid for eid in ep_ids if ep_ids.count(eid) > 1}
                errors.append(f"集 ID 重复: {dup}")

            # episode.scenes 引用有效性
            for ep in root.episodes:
                for sid in ep.scenes:
                    if sid not in valid_scene_ids:
                        errors.append(f"集 '{ep.episode_id}' 引用了不存在的场景 '{sid}'")

            # 统计一致性
            actual_eps = len(root.episodes)
            if root.metadata.total_episodes and root.metadata.total_episodes != actual_eps:
                errors.append(
                    f"metadata.total_episodes ({root.metadata.total_episodes}) 与实际集数 ({actual_eps}) 不符"
                )

        # 7. metadata 统计值
        actual_scenes = len(root.scenes)
        actual_beats = sum(len(s.beats) for s in root.scenes)
        if root.metadata.total_scenes != actual_scenes:
            errors.append(
                f"metadata.total_scenes ({root.metadata.total_scenes}) 与实际场景数 ({actual_scenes}) 不符"
            )
        if root.metadata.total_beats != actual_beats:
            errors.append(
                f"metadata.total_beats ({root.metadata.total_beats}) 与实际节拍数 ({actual_beats}) 不符"
            )

        return errors


# =============================================================================
# 辅助函数
# =============================================================================

def export_to_yaml(script_doc: ScriptDocument, path: Path | str) -> None:
    """将剧本文档导出为 YAML 文件"""
    script_doc.save(path)


def validate_yaml_file(path: Path | str) -> tuple[bool, list[str]]:
    """
    校验 YAML 文件是否符合 Schema。
    返回 (是否通过, 错误信息列表)。
    """
    try:
        doc = ScriptDocument.from_file(path)
        errors = doc.validate_consistency()
        return len(errors) == 0, errors
    except Exception as e:
        return False, [f"Schema 校验失败: {e}"]
