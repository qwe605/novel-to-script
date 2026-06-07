"""
场景检测与对白提取引擎
提供两种模式：
  1. 规则模式（默认）：零成本，基于启发式规则进行场景分割和节拍提取
  2. AI 模式（可选）：调用 Claude API 进行高精度场景拆解
"""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from novel_parser import Chapter, ChapterOutline, NovelCharacter, ParsedNovel


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class DetectedBeat:
    """检测出的节拍（尚未分配 ID）"""
    type: str  # action | dialogue | transition | narration
    content: str
    character: Optional[str] = None
    parenthetical: Optional[str] = None
    is_dialogue: bool = False


@dataclass
class DetectedScene:
    """检测出的场景（尚未分配正式 ID）"""
    heading_location: str = "待设定地点"
    heading_time: str = "DAY"
    heading_int_ext: str = "INT."
    source_chapters: list[int] = field(default_factory=list)
    estimated_duration_seconds: int = 60
    scene_type: str = "dialogue_heavy"
    mood: str = ""
    beats: list[DetectedBeat] = field(default_factory=list)


@dataclass
class DetectionResult:
    """单章检测结果"""
    chapter_number: int
    scenes: list[DetectedScene] = field(default_factory=list)


# =============================================================================
# 规则模式：启发式场景检测器
# =============================================================================

class RuleBasedSceneDetector:
    """
    基于规则的零成本场景检测器。

    核心启发式规则：
    1. 对话检测：短段落（<=25字）或包含引号 → 对白候选
    2. 场景切换：出现时间/地点关键词 → 新场景候选
    3. 场景类型：连续短段落多 → dialogue_heavy；长段落多 → action
    4. 地点推断：从段落中提取地点关键词作为 heading_location
    """

    # 场景切换提示词（时间/空间转换信号）
    SCENE_TRANSITION_KEYWORDS = [
        r"第二天", r"次日", r"几天后", r"傍晚", r"深夜", r"清晨", r"黎明",
        r"同一时间", r"片刻后", r"与此同时", r"转场", r"切换",
        r"门外", r"屋内", r"房间里", r"走廊", r"大厅", r"庭院", r"车内",
        r"医院", r"办公室", r"公寓", r"别墅", r"咖啡厅", r"餐厅",
        r"来到", r"走进", r"走出", r"返回", r"离开",
    ]

    # 地点关键词库（用于 heading_location 推断）
    LOCATION_KEYWORDS = [
        # 室内具体空间
        (r"(?:别墅|公寓|出租屋|豪宅|小区|楼道|走廊|太平间)", "match", lambda m: m.group(0)),
        (r"(?:主卧|卧室|客厅|厨房|书房|浴室|洗手间|阳台|玄关)", "match", lambda m: m.group(0)),
        (r"(?:医院|诊所|病房|手术室|急诊室)", "match", lambda m: m.group(0)),
        (r"(?:办公室|会议室|公司|大厦|写字楼|大厅)", "match", lambda m: m.group(0)),
        (r"(?:咖啡厅|餐厅|酒吧|酒店|饭店|面馆|茶馆)", "match", lambda m: m.group(0)),
        (r"(?:车内|车上|车里|驾驶座|后座|出租车|公交车|地铁)", "match", lambda m: "车内"),
        # 室外场景
        (r"(?:工地|施工现场|街道|马路|路口|广场|公园|花园|庭院|小区门口|学校|大学|商场|超市)", "match", lambda m: m.group(0)),
        # 特定场景
        (r"(?:警察局|派出所|法院|银行|机场|车站|火车站|高铁站)", "match", lambda m: m.group(0)),
    ]

    # 地点介词提取 — "在/到+地点+里/内/中" 模式
    LOCATION_PREP_RE = re.compile(
        r"(?:在|到|走进|走出|返回|来到|回到|进入|离开|穿过|路过)"
        r"([一-鿿]{2,5}(?:别墅|公寓|房间|楼|层|室|厅|院|园|店|馆|厂|场|站|街|路|巷|区|村|镇))"
    )

    # 时间推断词
    TIME_KEYWORDS = {
        r"清晨|早上|早晨| dawn": "DAWN",
        r"白天|上午|中午|下午|日间": "DAY",
        r"傍晚|黄昏|日落| dusk": "DUSK",
        r"晚上|夜间|深夜|半夜|黑夜|夜幕": "NIGHT",
        r"稍后|片刻后|几分钟后|过了一会儿": "LATER",
        r"连续|紧接着|同时": "CONTINUOUS",
    }

    # 内外景推断
    INT_KEYWORDS = [r"房间", r"屋内", r"室内", r"别墅", r"公寓", r"出租屋", r"医院", r"办公室",
                    r"车内", r"车里", r"客厅", r"卧室", r"厨房", r"浴室", r"洗手间", r"走廊"]
    EXT_KEYWORDS = [r"街道", r"户外", r"室外", r"庭院", r"公园", r"广场", r"门外", r"工地",
                    r"施工现场", r"小区", r"路边", r"大街", r"马路", r"门口", r"路口"]

    # 对话引号模式
    DIALOGUE_PATTERNS = [
        re.compile(r"[\"\"']([^\"\"']+)[\"\"']"),           # "..." 或 '...'
        re.compile(r"[「『]([^」』]+)[」』]"),                  # 「...」或『...』
        re.compile(r"[（(]([^）)]+)[）)]"),                    # （...）——可能是内心独白
    ]

    def __init__(self, min_scene_duration: int = 30):
        self.min_scene_duration = min_scene_duration
        self._transition_regex = re.compile("|".join(self.SCENE_TRANSITION_KEYWORDS))
        self._int_regex = re.compile("|".join(self.INT_KEYWORDS))
        self._ext_regex = re.compile("|".join(self.EXT_KEYWORDS))

    def detect(self, chapter: "Chapter", outline: Optional["ChapterOutline"] = None) -> DetectionResult:
        """
        对单章进行场景检测。
        默认策略：一章 = 一个 Scene（简化处理，确保可用性）。
        如果检测到明确的场景切换信号，则拆分为多个 Scene。
        """
        paragraphs = self._split_paragraphs(chapter.content)
        if not paragraphs:
            return DetectionResult(chapter_number=chapter.number)

        # 尝试场景分割
        scene_blocks = self._split_scenes(paragraphs)

        scenes: list[DetectedScene] = []
        for block_idx, block in enumerate(scene_blocks):
            scene = self._build_scene(block, chapter.number, chapter.title, outline, block_idx)
            scenes.append(scene)

        return DetectionResult(chapter_number=chapter.number, scenes=scenes)

    def _split_paragraphs(self, text: str) -> list[str]:
        """将章节文本切分为段落列表"""
        lines = text.replace("\r\n", "\n").split("\n")
        paragraphs: list[str] = []
        for line in lines:
            line = line.strip()
            if line:
                paragraphs.append(line)
        return paragraphs

    def _split_scenes(self, paragraphs: list[str]) -> list[list[str]]:
        """
        基于场景切换信号将段落分块。
        简化策略：只在检测到强烈切换信号时才拆分，避免过度分割。
        """
        blocks: list[list[str]] = []
        current_block: list[str] = []

        for i, para in enumerate(paragraphs):
            # 检测是否是场景切换提示
            is_transition = self._is_scene_transition(para, i, paragraphs)

            if is_transition and current_block and len(current_block) >= 2:
                # 保存当前块，开始新块
                blocks.append(current_block)
                current_block = [para]
            else:
                current_block.append(para)

        if current_block:
            blocks.append(current_block)

        # 如果没有任何拆分且段落较多，尝试按对话密度拆分
        if len(blocks) == 1 and len(paragraphs) > 20:
            blocks = self._split_by_pacing(paragraphs)

        return blocks if blocks else [paragraphs]

    def _is_scene_transition(self, para: str, index: int, all_paras: list[str]) -> bool:
        """判断段落是否是场景切换信号"""
        # 强信号：显式的时间/地点转换词出现在段落开头
        if self._transition_regex.search(para[:20]):
            return True
        # 强信号：以"与此同时""另一边"等开头
        if re.search(r"^(与此同时|另一边|另一边|场景转换|切至)", para):
            return True
        return False

    def _split_by_pacing(self, paragraphs: list[str]) -> list[list[str]]:
        """按对话/叙述节奏变化拆分场景"""
        blocks: list[list[str]] = []
        current_block: list[str] = []
        prev_is_dialogue = False

        for para in paragraphs:
            is_dialogue = self._is_dialogue_paragraph(para)

            # 如果对话/叙述模式发生剧烈变化，考虑切分
            if current_block and is_dialogue != prev_is_dialogue and len(current_block) >= 5:
                blocks.append(current_block)
                current_block = [para]
            else:
                current_block.append(para)

            prev_is_dialogue = is_dialogue

        if current_block:
            blocks.append(current_block)
        return blocks

    def _is_dialogue_paragraph(self, para: str) -> bool:
        """判断段落是否极可能是对话"""
        if len(para) <= 25:
            return True
        # 包含引号
        if any(p.search(para) for p in self.DIALOGUE_PATTERNS):
            return True
        return False

    def _build_scene(
        self,
        paragraphs: list[str],
        chapter_number: int,
        chapter_title: Optional[str],
        outline: Optional["ChapterOutline"],
        block_index: int,
    ) -> DetectedScene:
        """将段落块构建为 DetectedScene"""
        scene = DetectedScene()
        scene.source_chapters = [chapter_number]

        # 推断 heading
        scene.heading_location = self._infer_location(paragraphs, chapter_title)
        scene.heading_time = self._infer_time(paragraphs, chapter_title)
        scene.heading_int_ext = self._infer_int_ext(paragraphs)

        # 推断 mood
        if outline and outline.emotion_arc:
            scene.mood = outline.emotion_arc
        elif outline and outline.mood_start:
            scene.mood = f"{outline.mood_start}→{outline.mood_end}"
        elif chapter_title and any(kw in chapter_title for kw in ["醒来","苏醒","震惊","恐慌","翻车","打脸","修罗"]):
            scene.mood = "紧张→警觉"

        # 推断 type
        dialogue_count = sum(1 for p in paragraphs if self._is_dialogue_paragraph(p))
        ratio = dialogue_count / len(paragraphs) if paragraphs else 0
        if ratio > 0.6:
            scene.scene_type = "dialogue_heavy"
        elif ratio < 0.2:
            scene.scene_type = "action"
        else:
            scene.scene_type = "static"

        # 预估时长（按段落数粗略估算：每段 ~3-5 秒）
        scene.estimated_duration_seconds = max(
            self.min_scene_duration,
            len(paragraphs) * 4
        )

        # 提取 beats
        scene.beats = self._extract_beats(paragraphs)

        return scene

    def _infer_location(self, paragraphs: list[str], chapter_title: Optional[str] = None) -> str:
        """从段落中推断地点，辅以章节标题"""
        full_text = "".join(paragraphs[:15])

        # 1. 地点关键词库
        for pattern, mode, extractor in self.LOCATION_KEYWORDS:
            m = re.search(pattern, full_text)
            if m:
                return extractor(m)

        # 2. "在/到 + 地点 + 里/内" 介词模式
        m = self.LOCATION_PREP_RE.search(full_text)
        if m:
            return m.group(1)

        # 3. "酒店/医院/公司/学校 + 名词" 组合
        compound_m = re.search(r"([一-鿿]{2,4}(?:酒店|医院|公司|学校|大厦|大楼|花园|小区))", full_text)
        if compound_m:
            return compound_m.group(1)

        # 4. 回退：章节标题 → 场景名（只取看起来像地名的短标题）
        if chapter_title:
            clean = re.sub(r"^[#第CcHh\d一二三四五六七八九十百千万]+[章节部回话集期]?\s*[：:。.]?\s*", "", chapter_title)
            clean = re.sub(r"^[\[【].*?[\]】]\s*", "", clean)
            clean = clean.strip()
            # 必须含地点特征词才采纳（避免"说清楚""他想起来了"等纯动作/对话标题）
            LOCATION_SUFFIX_RE = re.compile(
                r"(?:室|厅|房|楼|院|园|店|馆|场|站|街|路|巷|区|村|镇|城"
                r"|医院|学校|公司|酒店|餐厅|咖啡|超市|商场|公园|广场"
                r"|工地|工厂|车间|出租屋|别墅|公寓|豪宅|小区"
                r"|卧室|厨房|浴室|洗手间|走廊|电梯|楼梯|门口|路边|门)"
            )
            if clean and LOCATION_SUFFIX_RE.search(clean):
                return clean

        return "待设定地点"

    def _infer_time(self, paragraphs: list[str], chapter_title: Optional[str] = None) -> str:
        """从段落中推断时间，辅以章节标题"""
        full_text = "".join(paragraphs[:5])
        for pattern, time_val in self.TIME_KEYWORDS.items():
            if re.search(pattern, full_text):
                return time_val
        # 从章节标题推断
        if chapter_title:
            if any(kw in chapter_title for kw in ["深夜","夜晚","黑夜","夜"]):
                return "NIGHT"
            if any(kw in chapter_title for kw in ["清晨","黎明","早晨","晨"]):
                return "DAWN"
            if any(kw in chapter_title for kw in ["黄昏","傍晚","暮"]):
                return "DUSK"
        return "DAY"

    def _infer_int_ext(self, paragraphs: list[str]) -> str:
        """推断内景/外景"""
        full_text = "".join(paragraphs[:10])
        int_count = len(self._int_regex.findall(full_text))
        ext_count = len(self._ext_regex.findall(full_text))
        if ext_count > int_count:
            return "EXT."
        return "INT."

    def _extract_beats(self, paragraphs: list[str]) -> list[DetectedBeat]:
        """从段落中提取节拍"""
        beats: list[DetectedBeat] = []

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 尝试提取引号内对白
            dialogue_snippets = self._extract_dialogue_snippets(para)

            if dialogue_snippets and len(para) <= 40:
                # 整段主要是对话
                for snippet in dialogue_snippets:
                    beats.append(DetectedBeat(
                        type="dialogue",
                        content=snippet,
                        is_dialogue=True,
                    ))
            elif dialogue_snippets:
                # 混合段落：先动作，再对白
                action_part = para
                for snippet in dialogue_snippets:
                    action_part = action_part.replace(f'"{snippet}"', "").replace(f"'{snippet}'", "")
                    action_part = action_part.replace(f"「{snippet}」", "").replace(f"『{snippet}』", "")
                    action_part = action_part.replace(f"（{snippet}）", "")
                action_part = action_part.strip("，。 \n")
                if action_part and len(action_part) > 5:
                    beats.append(DetectedBeat(type="action", content=action_part))
                for snippet in dialogue_snippets:
                    beats.append(DetectedBeat(type="dialogue", content=snippet, is_dialogue=True))
            else:
                # 纯动作/叙述
                # 如果段落很短（<=15字），可能是动作提示
                # 如果段落很长，可能是叙述，需要拆或标记为 action
                beats.append(DetectedBeat(type="action", content=para))

        return beats

    def _extract_dialogue_snippets(self, para: str) -> list[str]:
        """提取引号内的对白片段"""
        snippets: list[str] = []
        seen = set()
        for pattern in self.DIALOGUE_PATTERNS:
            for match in pattern.finditer(para):
                text = match.group(1).strip()
                if text and text not in seen:
                    snippets.append(text)
                    seen.add(text)
        return snippets


# =============================================================================
# AI 模式：多提供商场景检测器
# =============================================================================

class AIStudioSceneDetector:
    """
    基于 LLM API 的高精度场景检测器。
    支持 Anthropic（原生 SDK）和 OpenAI-compatible 接口（DeepSeek, OpenAI, OpenRouter, 自定义）。

    参数:
        provider: "anthropic" | "openai" | "deepseek" | "openrouter" | "custom"
        api_key: API Key（也可通过环境变量设置）
        model: 模型名（默认使用 provider 内置默认模型）
        base_url: 自定义 base URL（可选，覆盖 provider 默认值）
        temperature: 采样温度
        max_tokens: 输出最大 token 数
    """

    # 提供商默认配置
    # ⚠️ CANONICAL SOURCE: backend/app/core/config.py → PROVIDER_CONFIGS
    # 此处的 base_url / default_model / api_type / env_key 必须与 canonical 一致。
    # model 列表不在此处维护（仅 backend API 对外暴露）。
    PROVIDER_DEFAULTS: dict[str, dict] = {
        "anthropic": {
            "base_url": "https://api.anthropic.com",
            "default_model": "claude-sonnet-4-6",
            "api_type": "anthropic",
            "env_key": "ANTHROPIC_API_KEY",
        },
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o",
            "api_type": "openai_compatible",
            "env_key": "OPENAI_API_KEY",
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com",
            "default_model": "deepseek-chat",
            "api_type": "openai_compatible",
            "env_key": "DEEPSEEK_API_KEY",
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "default_model": "openai/gpt-4o",
            "api_type": "openai_compatible",
            "env_key": "OPENROUTER_API_KEY",
        },
        "custom": {
            "base_url": "http://localhost:11434/v1",
            "default_model": "llama3",
            "api_type": "openai_compatible",
            "env_key": None,
        },
    }

    def __init__(
        self,
        provider: str = "deepseek",
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        provider = provider.lower()
        if provider not in self.PROVIDER_DEFAULTS:
            raise ValueError(
                f"未知提供商: {provider}。支持: {list(self.PROVIDER_DEFAULTS.keys())}"
            )

        pcfg = self.PROVIDER_DEFAULTS[provider]
        self.provider = provider
        self.api_type = pcfg["api_type"]
        self.base_url = (base_url or pcfg["base_url"]).rstrip("/")
        self.model = model or pcfg["default_model"]
        self.temperature = temperature
        self.max_tokens = max_tokens

        # API Key 优先级: 参数 > 环境变量(provider专属) > DEFAULT_AI_API_KEY
        env_key_name = pcfg.get("env_key")
        self.api_key = api_key
        if not self.api_key and env_key_name:
            self.api_key = os.environ.get(env_key_name)
        if not self.api_key:
            self.api_key = os.environ.get("DEFAULT_AI_API_KEY")

        if not self.api_key:
            raise RuntimeError(
                f"AI 模式需要 API Key。请提供 api_key 参数或设置环境变量 "
                f"{env_key_name or 'DEFAULT_AI_API_KEY'}。"
            )

        self._client = None

    def _get_client(self):
        """延迟初始化 API 客户端"""
        if self._client is not None:
            return self._client

        if self.api_type == "anthropic":
            try:
                import anthropic
            except ImportError:
                raise RuntimeError(
                    "Anthropic 提供商需要 anthropic 库。请运行: pip install anthropic"
                )
            self._client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        else:
            # OpenAI-compatible
            try:
                from openai import OpenAI
            except ImportError:
                raise RuntimeError(
                    "OpenAI-compatible 提供商需要 openai 库。请运行: pip install openai"
                )
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    def detect(self, chapter: "Chapter", outline: Optional["ChapterOutline"] = None) -> DetectionResult:
        """
        混合模式：
        - AI 负责：场景边界识别、地点/时间/情绪推断、角色归因
        - 规则引擎负责：在每个 AI 识别的 scene 内机械提取 beats
        """
        system_prompt = """你是一位专业的网文改编编剧大师，精通将小说文本转换为结构化剧本。
你的核心理念：以视觉构建文本，以戏剧动作为基本单位，用潜台词替代直白表达。

## 输出格式

严格输出一个 JSON 对象（不要任何解释、markdown 标记或多余文本），只返回场景级信息，不要 beats 内容：
{
  "scenes": [
    {
      "location": "具体地点（细化到可定位的子空间，如'别墅-主卧'而非'房间'）",
      "time": "DAY | NIGHT | DAWN | DUSK | LATER | CONTINUOUS",
      "int_ext": "INT. | EXT. | INT./EXT.",
      "scene_type": "dialogue_heavy | action | montage | transition | static",
      "mood": "场景情绪弧线，如'压抑→警觉'或'试探→紧张'（可为空字符串）",
      "characters": ["角色1", "角色2"]
    }
  ]
}

## 编剧铁律（违反即不合格）

### 绝对禁止
1. **心理描写**：不得出现"他意识到""她感到""内心涌起""我想""他觉得"等无法被摄影机捕捉的心理活动。
2. **括号暗示**：parenthetical 不得包含解释角色内心的内容，如"（其实是在掩饰紧张）"。
3. **角色用台词解释设定**：台词必须服务于角色间的冲突或关系，不是作者的传声筒。

### 必须做到
- 只写能被看见的动作和能被听见的声音
- 用具体动作替代心理描写（动作即潜台词）
- 对白口语化、自然、像真人说话

## Scene 拆分规则

1. 时空统一性：同一地点 + 连续时间 = 同一个 Scene。时间跳跃或地点转换 → 新 Scene。
2. 情绪转折：当场景情绪发生质变（如从平静→激烈冲突），即使同一地点也应考虑拆分。
3. scene_type 判断标准：
   - dialogue_heavy：对白占比 > 60%（连续短段落、多引号）
   - action：动作/描写占比 > 60%（长段落、大量动作描写）
   - montage：时间压缩型（多个短片段快速切换）
   - transition：纯转场过渡（无实质内容）
   - static：静止/氛围场景（环境描写为主，无冲突）

## 角色归因规则

1. 角色名使用原文中的名字（如"林婉""顾深寒"），不要自创。
2. 同一角色在全文使用统一的名字，不要有时用全名有时用简称。
3. 每个 scene 的 characters 数组列出该场景出现的所有角色。
4. 第一人称"我"→ 用实际角色名替代。

## 从小说文本转换的实操指南

1. 引号内的对话 → 推断说话角色
2. 环境/氛围描写 → 提取为 scene 的地点信息
3. 心理活动 → 判断是否能转为视觉动作，填入 mood 中
4. 保持原文语言风格，不要改写或美化原文
"""

        content = (chapter.content or "")

        # 构建章节上下文提示
        ctx_parts: list[str] = []
        if chapter.title:
            ctx_parts.append(f"章节标题：{chapter.title}")
        if outline:
            if outline.main_event:
                ctx_parts.append(f"主事件：{outline.main_event}")
            if outline.emotion_arc:
                ctx_parts.append(f"情绪弧线：{outline.emotion_arc}")

        user_prompt = ""
        if ctx_parts:
            user_prompt += "\n".join(ctx_parts) + "\n\n"
        user_prompt += f"小说章节内容：\n\n{content}\n\n"
        user_prompt += "只返回 scenes 数组，每个 scene 含 location/time/int_ext/scene_type/mood/characters 字段。不要 beats。"

        if self.api_type == "anthropic":
            raw = self._call_anthropic(system_prompt, user_prompt)
        else:
            raw = self._call_openai_compatible(system_prompt, user_prompt)

        # 提取 JSON
        import json
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"AI 返回了非标准 JSON，请重试或切换为规则模式。原始内容前 200 字符: {raw[:200]}") from e

        # AI 返回场景元数据 → 按比例分配段落 → 规则引擎填充 beats
        all_paras = _split_paragraphs(content)
        scene_metas = [d for d in (data.get("scenes") or []) if isinstance(d, dict)]
        n_scenes = max(1, len(scene_metas))
        scenes: list[DetectedScene] = []

        for idx, sc_data in enumerate(scene_metas):
            # 每个 AI 识别的 scene 分到 1/n 的段落（不重叠）
            start = idx * len(all_paras) // n_scenes
            end = (idx + 1) * len(all_paras) // n_scenes if idx < n_scenes - 1 else len(all_paras)
            paras = all_paras[start:end]

            characters = sc_data.get("characters") or []
            char_names = set(characters)

            beats = _rule_extract_beats(paras, char_names)

            scenes.append(DetectedScene(
                heading_location=(sc_data.get("location") or "待设定地点"),
                heading_time=(sc_data.get("time") or "DAY"),
                heading_int_ext=(sc_data.get("int_ext") or "INT."),
                source_chapters=[chapter.number],
                scene_type=(sc_data.get("scene_type") or "dialogue_heavy"),
                mood=(sc_data.get("mood") or ""),
                beats=beats,
            ))

        return DetectionResult(chapter_number=chapter.number, scenes=scenes)

    def _call_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text

    def _call_openai_compatible(self, system_prompt: str, user_prompt: str) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""


# =============================================================================
# 混合模式辅助 — AI 做场景边界，规则引擎填充 beat
# =============================================================================

def _split_paragraphs(text: str) -> list[str]:
    """将文本切分为段落列表"""
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return [line.strip() for line in lines if line.strip()]


def _is_dialogue_para(para: str) -> bool:
    """判断段落是否为对话"""
    if len(para) <= 25:
        return True
    if re.search(r"[\"\"''「『](.+?)[\"\"''」『]", para):
        return True
    return False


def _extract_dialogue_snippets(para: str) -> list[str]:
    """从段落提取引号内的对白"""
    seen: set[str] = set()
    snippets: list[str] = []
    for pat in [r"[\"\"]([^\"\"]+)[\"\"]", r"[「『]([^」』]+)[」』]"]:
        for m in re.finditer(pat, para):
            t = m.group(1).strip()
            if t and t not in seen:
                snippets.append(t)
                seen.add(t)
    return snippets


def _rule_extract_beats(paragraphs: list[str], known_characters: set[str] | None = None) -> list[DetectedBeat]:
    """规则引擎从段落中提取 beats，用 AI 提供的角色名辅助归因"""
    beats: list[DetectedBeat] = []
    chars = known_characters or set()

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        snippets = _extract_dialogue_snippets(para)

        if snippets and len(para) <= 40:
            # 整段主要是对话
            for s in snippets:
                # 尝试从上下文匹配角色
                char = None
                for c in chars:
                    if c in para[:20]:
                        char = c
                        break
                beats.append(DetectedBeat(type="dialogue", content=s, character=char, is_dialogue=True))
        elif snippets:
            # 混合段落：先提取动作部分，再放对白
            action_part = para
            for s in snippets:
                action_part = action_part.replace(f'"”{s}“', "").replace(f"'{s}'", "")
                action_part = action_part.replace(f"「{s}」", "").replace(f"『{s}』", "")
            action_part = action_part.strip("，。 \n")
            if action_part and len(action_part) > 5:
                beats.append(DetectedBeat(type="action", content=action_part))
            for s in snippets:
                char = None
                for c in chars:
                    if c in para[:30]:
                        char = c
                        break
                beats.append(DetectedBeat(type="dialogue", content=s, character=char, is_dialogue=True))
        else:
            beats.append(DetectedBeat(type="action", content=para))

    return beats


# =============================================================================
# 便捷入口
# =============================================================================

def detect_scenes(
    novel: "ParsedNovel",
    mode: str = "rule",
    api_key: Optional[str] = None,
    provider: str = "deepseek",
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    max_concurrency: int = 6,
) -> list[DetectionResult]:
    """
    对整部小说进行场景检测。

    AI 模式：多章节并发调用 API，大幅缩短总耗时。
    55 章串行 ≈ 3 分钟 → 6 并发 ≈ 30 秒。

    Args:
        novel: 解析后的小说对象
        mode: "rule" 或 "ai"
        api_key: AI 模式所需的 API Key（也可通过环境变量设置）
        provider: AI 提供商
        model: 模型名
        base_url: 自定义 base_url
        temperature: AI 采样温度
        max_tokens: 输出 token 上限
        max_concurrency: AI 模式最大并发数（默认 6）

    Returns:
        每章的检测结果列表（保持原顺序）
    """
    if mode == "ai":
        # 创建 detector 实例（每个线程独立使用不同的实例避免状态竞争）
        def _create_detector():
            return AIStudioSceneDetector(
                provider=provider,
                api_key=api_key,
                model=model,
                base_url=base_url,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        # 多线程并发调用 API
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results_map: dict[int, DetectionResult] = {}

        def _detect_one(chapter, outline):
            detector = _create_detector()
            return detector.detect(chapter, outline)

        with ThreadPoolExecutor(max_workers=min(max_concurrency, len(novel.chapters))) as pool:
            futures = {
                pool.submit(_detect_one, chapter, novel.get_outline(chapter.number)): chapter.number
                for chapter in novel.chapters
            }
            for future in as_completed(futures):
                ch_num = futures[future]
                results_map[ch_num] = future.result()

        # 保持原顺序返回
        return [results_map[ch.number] for ch in novel.chapters if ch.number in results_map]

    # 规则模式：串行即可（很快）
    detector = RuleBasedSceneDetector()
    results: list[DetectionResult] = []
    for chapter in novel.chapters:
        outline = novel.get_outline(chapter.number)
        results.append(detector.detect(chapter, outline))
    return results
