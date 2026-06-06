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
        (r"(.*?)(?:别墅|公寓|房子|房间|卧室|客厅|厨房|书房|浴室)", r"\1\2"),
        (r"(.*?)(?:医院|诊所|病房|手术室)", r"医院 - \2"),
        (r"(.*?)(?:办公室|会议室|公司|大厦)", r"公司 - \2"),
        (r"(.*?)(?:咖啡厅|餐厅|酒吧|酒店)", r"\1\2"),
        (r"(.*?)(?:车内|车外|车里|驾驶座|后座)", r"车内"),
        (r"(.*?)(?:街道|马路|路口|广场|公园)", r"街道"),
    ]

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
    INT_KEYWORDS = [r"房间", r"屋内", r"室内", r"别墅", r"公寓", r"医院", r"办公室", r"车内"]
    EXT_KEYWORDS = [r"街道", r"户外", r"室外", r"庭院", r"公园", r"广场", r"门外"]

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
            scene = self._build_scene(block, chapter.number, outline, block_idx)
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
        outline: Optional["ChapterOutline"],
        block_index: int,
    ) -> DetectedScene:
        """将段落块构建为 DetectedScene"""
        scene = DetectedScene()
        scene.source_chapters = [chapter_number]

        # 推断 heading
        scene.heading_location = self._infer_location(paragraphs)
        scene.heading_time = self._infer_time(paragraphs)
        scene.heading_int_ext = self._infer_int_ext(paragraphs)

        # 推断 mood
        if outline and outline.emotion_arc:
            scene.mood = outline.emotion_arc
        elif outline and outline.mood_start:
            scene.mood = f"{outline.mood_start}→{outline.mood_end}"

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

    def _infer_location(self, paragraphs: list[str]) -> str:
        """从段落中推断地点"""
        full_text = "".join(paragraphs[:10])  # 只看前10段
        for pattern, _ in self.LOCATION_KEYWORDS:
            m = re.search(pattern, full_text)
            if m:
                loc = m.group(0)
                # 简化地点名
                loc = re.sub(r"^(.*?)(?:的|里|内|中)", r"\1", loc)
                return loc[-10:]  # 限制长度
        return "待设定地点"

    def _infer_time(self, paragraphs: list[str]) -> str:
        """从段落中推断时间"""
        full_text = "".join(paragraphs[:5])
        for pattern, time_val in self.TIME_KEYWORDS.items():
            if re.search(pattern, full_text):
                return time_val
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
        调用 LLM API 进行高精度场景拆解。
        返回结构和 RuleBasedSceneDetector 完全一致。
        """
        system_prompt = """你是一位专业的网文改编编剧大师，精通将小说文本转换为结构化剧本。
你的核心理念：以视觉构建文本，以戏剧动作为基本单位，用潜台词替代直白表达。

## 输出格式

严格输出一个 JSON 对象（不要任何解释、markdown 标记或多余文本）：
{
  "scenes": [
    {
      "location": "具体地点（细化到可定位的子空间，如'别墅-主卧'而非'房间'）",
      "time": "DAY | NIGHT | DAWN | DUSK | LATER | CONTINUOUS",
      "int_ext": "INT. | EXT. | INT./EXT.",
      "scene_type": "dialogue_heavy | action | montage | transition | static",
      "mood": "场景情绪弧线，如'压抑→警觉'或'试探→紧张'（可为空字符串）",
      "beats": [
        {
          "type": "action | dialogue | narration | vos | transition | sfx | music",
          "content": "具体内容",
          "character": "角色名（仅 dialogue/action 类型需要，其他类型为 null）",
          "parenthetical": "括号提示（仅 dialogue 类型可选，如'压低声音''停顿'，可为 null）"
        }
      ]
    }
  ]
}

## 编剧铁律（违反即不合格）

### 绝对禁止
1. **心理描写**：不得出现"他意识到""她感到""内心涌起""我想""他觉得"等无法被摄影机捕捉的心理活动。
   错误示例："林婉感到一阵恐惧涌上心头。"
   正确做法："林婉的手指攥紧被角，指节发白。"
2. **括号暗示**：parenthetical 不得包含解释角色内心的内容，如"（其实是在掩饰紧张）"。
3. **角色用台词解释设定**：台词必须服务于角色间的冲突或关系，不是作者的传声筒。
4. **AI 腔台词**：禁止过度比喻、书面化长句、散文式表达。台词要像真人说话。

### 必须做到
- 只写能被看见的动作和能被听见的声音
- 用具体动作替代心理描写（动作即潜台词）
- 对白口语化、自然、像真人说话
- 对话是冰山——角色说出来的只是表面，真正的含义在水面之下

## Scene 拆分规则

1. 时空统一性：同一地点 + 连续时间 = 同一个 Scene。时间跳跃或地点转换 → 新 Scene。
2. 情绪转折：当场景情绪发生质变（如从平静→激烈冲突），即使同一地点也应考虑拆分。
3. scene_type 判断标准：
   - dialogue_heavy：对白占比 > 60%（连续短段落、多引号）
   - action：动作/描写占比 > 60%（长段落、大量动作描写）
   - montage：时间压缩型（多个短片段快速切换）
   - transition：纯转场过渡（无实质内容）
   - static：静止/氛围场景（环境描写为主，无冲突）

## Beat 类型选择

| type | 使用场景 | 示例 |
|------|---------|------|
| action | 角色动作、环境变化、视觉呈现 | "林婉猛然睁眼，手指抓向枕边" |
| dialogue | 角色说出的台词 | "醒了？"（直接引用原文对话） |
| narration | 旁白/画外音（非角色声音，叙述性文字） | "三年后，这座城市变了模样" |
| vos | 角色内心独白，以画外音形式呈现 | 第一人称内心活动转 VO |
| transition | 场景转换 | 仅用于特殊转场，普通场景切换在 scene 级别处理 |
| sfx | 重点音效提示 | "雷声由远及近" |
| music | 音乐提示 | 仅在有明确音乐描述时使用 |

## 角色归因规则

1. 对白必须归因到说话的角色。从上下文推断说话者（引号前的人名、"XX说"等）。
2. 动作为特定角色的动作时填写 character，环境描写/群体动作时可为 null。
3. 角色名使用原文中的名字（如"林婉""顾深寒"），不要自创。
4. 同一角色在全文使用统一的名字，不要有时用全名有时用简称。

## 从小说文本转换的实操指南

1. **第一人称转换**：小说中"我"的内心独白 → 根据语境转为 action（可视动作）、vos（内心独白 VO）、或 narration（旁白）。
   示例："我攥了攥拳头，走进了小区。" → type: action, content: "她攥了攥拳头，走进小区。"
   示例："我想，我必须找到他。" → type: vos, content: "我必须找到他。"

2. **引号内对话**：直接提取为 dialogue beat，去除引号，保留原汁原味的台词。
3. **环境/氛围描写**：转为 action beat，保留视觉细节。
4. **parenthetical 使用**：仅在对白中标注语气或极简动作（≤10 个中文字符）。禁止解释心理。
   正确："（压低声音）""（停顿）""（尾音微扬）"
   错误："（内心其实很害怕）""（这句话是在试探对方）"

5. **保持原文语言风格**：不要改写或美化原文，保持小说原有的语气和节奏。
"""

        user_prompt = f"小说章节内容：\n\n{chapter.content}\n\n"
        if outline:
            user_prompt += f"\n章节大纲信息：\n主事件：{outline.main_event}\n情绪弧线：{outline.emotion_arc}\n"

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

        data = json.loads(raw)
        scenes: list[DetectedScene] = []

        for sc_data in data.get("scenes", []):
            scene = DetectedScene(
                heading_location=sc_data.get("location", "待设定地点"),
                heading_time=sc_data.get("time", "DAY"),
                heading_int_ext=sc_data.get("int_ext", "INT."),
                source_chapters=[chapter.number],
                scene_type=sc_data.get("scene_type", "dialogue_heavy"),
                mood=sc_data.get("mood", ""),
            )
            for b_data in sc_data.get("beats", []):
                scene.beats.append(DetectedBeat(
                    type=b_data.get("type", "action"),
                    content=b_data.get("content", ""),
                    character=b_data.get("character") or None,
                    is_dialogue=b_data.get("type") == "dialogue",
                ))
            scene.estimated_duration_seconds = max(30, len(scene.beats) * 5)
            scenes.append(scene)

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
) -> list[DetectionResult]:
    """
    对整部小说进行场景检测。

    Args:
        novel: 解析后的小说对象
        mode: "rule" 或 "ai"
        api_key: AI 模式所需的 API Key（也可通过环境变量设置）
        provider: AI 提供商（anthropic/openai/deepseek/openrouter/custom）
        model: 模型名（可选，不传则使用 provider 默认）
        base_url: 自定义 base_url（可选）
        temperature: AI 采样温度
        max_tokens: 输出 token 上限

    Returns:
        每章的检测结果列表
    """
    if mode == "ai":
        detector: RuleBasedSceneDetector | AIStudioSceneDetector = AIStudioSceneDetector(
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        detector = RuleBasedSceneDetector()

    results: list[DetectionResult] = []
    for chapter in novel.chapters:
        outline = novel.get_outline(chapter.number)
        result = detector.detect(chapter, outline)
        results.append(result)

    return results
