"""
小说解析模块
支持解析 notel 项目结构（正文.md + 设定.md + 小节大纲.md），
也支持解析任意文本文件（自动识别章节分隔符）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# 中文章节序号 → 数字
_ZH_NUMS: dict[str, int] = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    "十一": 11, "十二": 12, "十三": 13, "十四": 14,
    "十五": 15, "十六": 16, "十七": 17, "十八": 18,
    "十九": 19, "二十": 20, "二十一": 21, "二十二": 22,
    "二十三": 23, "二十四": 24, "二十五": 25,
    "二十六": 26, "二十七": 27, "二十八": 28,
    "二十九": 29, "三十": 30,
    "三十一":31,"三十二":32,"三十三":33,"三十四":34,"三十五":35,
    "三十六":36,"三十七":37,"三十八":38,"三十九":39,"四十":40,
    "四十一":41,"四十二":42,"四十三":43,"四十四":44,"四十五":45,
    "四十六":46,"四十七":47,"四十八":48,"四十九":49,"五十":50,
}
# 补充 0-9，百位模式用正则处理
for i in range(10):
    _ZH_NUMS[str(i)] = i


def _parse_zh_num(s: str) -> int | None:
    """解析中文章节号 → 数字。'## 第一章' → 1, '第30章' → 30, '第一百二十章' → 120"""
    m = re.search(r"第\s*([\d零一二三四五六七八九十百千万]+)\s*章", s)
    if not m:
        return None
    raw = m.group(1)
    # 纯数字
    if raw.isdigit():
        return int(raw)
    # 中文数字 — 片付け
    result = 0
    current = 0
    for ch in raw:
        if ch in _ZH_NUMS:
            current = _ZH_NUMS[ch]
        elif ch == "十":
            current = current * 10 if current else 10
        elif ch == "百":
            current = (current or 1) * 100
            result += current
            current = 0
        elif ch == "千":
            current = (current or 1) * 1000
            result += current
            current = 0
        elif ch == "万":
            current = (current or 1) * 10000
            result += current
            current = 0
    result += current
    return result if result > 0 else None


def _split_rel_type_desc(text: str) -> tuple[str, str]:
    """拆分关系描述中的类型和详情。
    "恋人（两情相悦）" → ("恋人", "两情相悦")
    "敌人/死对头" → ("敌人", "死对头")
    "闺蜜" → ("闺蜜", "")
    """
    text = text.strip()
    # 括号内的详情
    m = re.match(r"(.+?)[（(](.+)[）)]", text)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    # 斜杠分割的类型
    if "/" in text:
        parts = text.split("/", 1)
        return parts[0].strip(), parts[1].strip()
    return text, ""


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class Chapter:
    """小说章节"""
    number: int
    title: Optional[str] = None
    content: str = ""


@dataclass
class CharacterRelationship:
    """角色关系"""
    target_name: str = ""           # 关系对象名
    relation_type: str = ""         # 关系类型：恋人/朋友/敌人/家人/师徒/...
    description: str = ""           # 关系描述
    intensity: str = ""             # 关系强度：亲密/一般/紧张/敌对/复杂


@dataclass
class NovelCharacter:
    """从设定.md 解析出的角色信息"""
    name: str
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    voice_tags: list[str] = field(default_factory=list)
    archetype: str = ""
    personality_traits: list[str] = field(default_factory=list)    # 性格特点
    relationships: list[CharacterRelationship] = field(default_factory=list)  # 角色关系
    role: str = ""                  # 角色定位：主角/反派/配角/...
    appearance: str = ""            # 外貌特征描述


@dataclass
class ChapterOutline:
    """从大纲解析出的章级元数据"""
    number: int
    title: Optional[str] = None
    main_event: str = ""
    sub_events: list[str] = field(default_factory=list)
    emotion_arc: str = ""          # 情绪：起点→终点
    mood_start: str = ""           # 情绪起点
    mood_end: str = ""             # 情绪终点
    hook: str = ""
    foreshadowing: str = ""
    pacing: str = ""               # 动静
    dialogue_density: str = ""     # 零/低/中/高
    target_word_count: int = 0


@dataclass
class ParsedNovel:
    """解析后的小说完整数据"""
    title: str = ""
    source_path: Optional[Path] = None
    chapters: list[Chapter] = field(default_factory=list)
    characters: list[NovelCharacter] = field(default_factory=list)
    outlines: list[ChapterOutline] = field(default_factory=list)

    def get_chapter(self, number: int) -> Optional[Chapter]:
        for ch in self.chapters:
            if ch.number == number:
                return ch
        return None

    def get_outline(self, number: int) -> Optional[ChapterOutline]:
        for ol in self.outlines:
            if ol.number == number:
                return ol
        return None


# =============================================================================
# 正文解析器
# =============================================================================

class NovelTextParser:
    """通用小说文本解析器"""

    # 支持的章节分隔符正则（按优先级）
    DELIMITER_PATTERNS = [
        (r"^###\s*(\d+)\.(.*)$", "notel"),           # ###1. 或 ###1.标题
        (r"^第\s*(\d+)\s*章[：: ]\s*(.*)$", "zh_chapter"),  # 第1章：标题
        (r"^第\s*(\d+)\s*章\s*(.*)$", "zh_chapter2"),      # 第1章 标题
        (r"^Chapter\s+(\d+)[:. ]\s*(.*)$", "en_chapter"),  # Chapter 1: Title
    ]
    # 通用章节头 — 阿拉伯数字 + 中文数字，统一捕获第X章
    HASH_CHAPTER_RE = re.compile(
        r"^##?\s*第\s*([\d零一二三四五六七八九十百千万]+)\s*章\s*(.*)$", re.MULTILINE
    )

    def parse_file(self, path: Path | str) -> list[Chapter]:
        """从文件解析章节列表，自动处理编码错误"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")
        if path.stat().st_size == 0:
            raise ValueError(f"文件为空: {path}")
        text = self._read_with_encoding_fallback(path)
        return self.parse_text(text)

    @staticmethod
    def _read_with_encoding_fallback(path: Path) -> str:
        """尝试多种编码读取文件"""
        for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312", "gb18030", "latin-1"):
            try:
                return path.read_text(encoding=enc)
            except (UnicodeDecodeError, UnicodeError):
                continue
        raw = path.read_bytes()
        return raw.decode("utf-8", errors="replace")

    def parse_text(self, text: str) -> list[Chapter]:
        """从文本解析章节列表"""
        if not text or not text.strip():
            raise ValueError("输入文本为空，无法解析")

        # 统一换行符
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Step 1: 尝试数字章节分隔符
        for pattern, pattern_name in self.DELIMITER_PATTERNS:
            chapters = self._try_split(text, pattern)
            if len(chapters) >= 1:
                if len(chapters) > 1 or chapters[0].number != 0:
                    return [ch for ch in chapters if ch.content.strip()]

        # Step 2: 尝试 ## 第N章（阿拉伯+中文数字混合）
        chapters = self._try_split_zh(text)
        if len(chapters) >= 2:
            return [ch for ch in chapters if ch.content.strip()]

        # 兜底：没有分隔符时，整段文本作为第 1 章
        text = text.strip()
        if not text:
            raise ValueError("输入文本解析后为空")
        return [Chapter(number=1, content=text)]

    def _try_split(self, text: str, pattern: str) -> list[Chapter]:
        """尝试用指定正则分割章节"""
        regex = re.compile(pattern, re.MULTILINE)
        matches = list(regex.finditer(text))

        if not matches:
            return []

        chapters: list[Chapter] = []
        for i, match in enumerate(matches):
            number = int(match.group(1))
            if number <= 0 or number > 100000:
                continue
            title = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else None
            if title and len(title) > 200:
                title = title[:200]
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            if not content:
                continue
            chapters.append(Chapter(number=number, title=title, content=content))

        return chapters

    def _try_split_zh(self, text: str) -> list[Chapter]:
        """用 ## 第N章 切分，支持阿拉伯数字和中文数字混排"""
        matches = list(self.HASH_CHAPTER_RE.finditer(text))
        if len(matches) < 2:
            # 单章不切
            return []

        chapters: list[Chapter] = []
        for i, match in enumerate(matches):
            num = _parse_zh_num(match.group(0))
            if num is None or num <= 0 or num > 10000:
                continue
            title = match.group(2).strip() if match.group(2) else None
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            if not content:
                continue
            chapters.append(Chapter(number=num, title=title, content=content))
        return chapters


# =============================================================================
# Notel 项目解析器
# =============================================================================

class NotelProjectParser:
    """
    解析 notel 标准项目结构：
        {书名}/
            正文.md
            设定.md
            小节大纲.md
    """

    def __init__(self, project_dir: Path | str):
        self.project_dir = Path(project_dir)
        if not self.project_dir.exists():
            raise FileNotFoundError(f"项目目录不存在: {self.project_dir}")
        if not self.project_dir.is_dir():
            raise NotADirectoryError(f"不是有效目录: {self.project_dir}")
        self.title = self.project_dir.name

    @staticmethod
    def _safe_read(path: Path) -> str | None:
        """安全读取文件，多编码尝试"""
        if not path.exists():
            return None
        for enc in ("utf-8", "utf-8-sig", "gbk", "gb2312", "gb18030", "latin-1"):
            try:
                return path.read_text(encoding=enc)
            except (UnicodeDecodeError, UnicodeError):
                continue
        raw = path.read_bytes()
        return raw.decode("utf-8", errors="replace")

    def parse(self) -> ParsedNovel:
        """解析整个 notel 项目"""
        novel = ParsedNovel(title=self.title, source_path=self.project_dir)

        # 1. 解析正文
        text_path = self.project_dir / "正文.md"
        content = self._safe_read(text_path)
        if content:
            parser = NovelTextParser()
            novel.chapters = parser.parse_text(content)

        # 2. 解析设定
        setting_path = self.project_dir / "设定.md"
        content = self._safe_read(setting_path)
        if content:
            novel.characters = self._parse_setting(content)

        # 3. 解析大纲
        outline_path = self.project_dir / "小节大纲.md"
        content = self._safe_read(outline_path)
        if content:
            novel.outlines = self._parse_outline(content)

        return novel

    def _parse_setting(self, text: str) -> list[NovelCharacter]:
        """从设定.md 文本内容提取角色信息"""
        if not text or not text.strip():
            return []
        characters: list[NovelCharacter] = []

        # 策略：先定位 "## 人设" 区域，只在该区域内解析 ### 三级标题
        # 人设区域可能以 "## 人设" 或 "## 角色" 开头，到下一个 ## 或文件结束为止
        persona_match = re.search(
            r"##\s*(人设|角色).*?\n(.*?)(?=\n##\s|\Z)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if not persona_match:
            # 回退：全文搜索 ### 角色标题（旧格式兼容）
            persona_block = text
        else:
            persona_block = persona_match.group(2)

        # 在人设区域内用 ### 分割角色
        char_sections = re.split(r"\n###\s*", persona_block)
        if len(char_sections) <= 1:
            # 回退到 **加粗** 格式
            char_sections = re.split(r"\n\*\*\s*", persona_block)

        for section in char_sections:
            section = section.strip()
            if not section:
                continue

            lines = section.split("\n")
            first_line = lines[0].strip().strip("*# ")
            if not first_line:
                continue

            # 过滤掉非角色标题（如"设定"、"基本信息"等）
            skip_keywords = ["设定", "基本", "信息", "故事核", "核心反转",
                             "结构物件", "对标", "摘要", "世界观"]
            if any(kw in first_line for kw in skip_keywords) or len(first_line) > 30:
                continue

            char = NovelCharacter(name=first_line)

            # 解析属性行
            for line in lines[1:]:
                line = line.strip()
                if line.startswith("-") or line.startswith("*"):
                    line = line.lstrip("-* ").strip()

                    if "描述" in line or "简介" in line or "身份" in line:
                        char.description = self._extract_value(line)
                    elif "语言" in line or "声音" in line or "说话" in line or "口吻" in line:
                        tags = self._extract_tags(line)
                        char.voice_tags.extend(tags)
                    elif "原型" in line or "类型" in line or " archetype" in line.lower():
                        char.archetype = self._extract_value(line)
                    elif "别名" in line or "昵称" in line:
                        char.aliases = self._extract_tags(line)
                    elif "性格" in line:
                        char.personality_traits = self._extract_tags(line)
                    elif "定位" in line or "角色" in line:
                        char.role = self._extract_value(line)
                    elif "外貌" in line or "外观" in line or "长相" in line:
                        char.appearance = self._extract_value(line)
                    elif "关系" in line:
                        # 关系格式: "关系：角色名（恋人/敌人），角色名（朋友）"
                        rel_text = self._extract_value(line)
                        char.relationships = self._parse_relationships(rel_text)

            characters.append(char)

        # 过滤掉太短的（可能是误匹配）
        characters = [c for c in characters if len(c.name) >= 2]
        return characters

    def _parse_outline(self, text: str) -> list[ChapterOutline]:
        """从小节大纲.md 文本内容提取章级元数据"""
        if not text or not text.strip():
            return []
        outlines: list[ChapterOutline] = []

        # 匹配 "### 第N章：标题" 或 "### 第N章 标题"
        pattern = re.compile(r"###\s*第\s*(\d+)\s*章[：:\s]*(.*)")
        sections = list(pattern.finditer(text))

        for i, match in enumerate(sections):
            number = int(match.group(1))
            title = match.group(2).strip() if match.group(2) else None
            start = match.end()
            end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
            section_text = text[start:end]

            ol = ChapterOutline(number=number, title=title)
            ol = self._parse_outline_section(section_text, ol)
            outlines.append(ol)

        return outlines

    def _parse_outline_section(self, text: str, ol: ChapterOutline) -> ChapterOutline:
        """解析单章大纲内容"""
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue

            # 主事件：...
            if line.startswith("主事件") or "主事件：" in line:
                ol.main_event = self._extract_value(line)

            # 情绪：起点→终点
            elif line.startswith("情绪") or "情绪：" in line:
                ol.emotion_arc = self._extract_value(line)
                # 尝试解析 起点→终点
                if "→" in ol.emotion_arc:
                    parts = ol.emotion_arc.split("→")
                    ol.mood_start = parts[0].strip()
                    ol.mood_end = parts[1].strip()

            # 钩子：...
            elif line.startswith("钩子") or "钩子：" in line:
                ol.hook = self._extract_value(line)

            # 伏笔/物件：...
            elif "伏笔" in line or "物件" in line:
                ol.foreshadowing = self._extract_value(line)

            # 动静：动/静
            elif line.startswith("动静") or "动静：" in line:
                ol.pacing = self._extract_value(line)

            # 对话密度：...
            elif "对话密度" in line:
                ol.dialogue_density = self._extract_value(line)

            # 目标字数：NNN字
            elif "目标字数" in line or "字数" in line:
                val = self._extract_value(line)
                digits = re.search(r"\d+", val)
                if digits:
                    ol.target_word_count = int(digits.group())

            # 子事件：{...} -> ...
            elif line.startswith("子事件") or "子事件：" in line:
                val = self._extract_value(line)
                ol.sub_events = [e.strip() for e in val.split("->") if e.strip()]

        return ol

    @staticmethod
    def _extract_value(line: str) -> str:
        """从 '键：值' 格式中提取值"""
        if "：" in line:
            return line.split("：", 1)[1].strip()
        if ":" in line:
            return line.split(":", 1)[1].strip()
        return line.strip()

    @staticmethod
    def _extract_tags(line: str) -> list[str]:
        """从行中提取逗号/顿号分隔的标签"""
        val = NotelProjectParser._extract_value(line)
        # 支持中文逗号、顿号、英文逗号分隔
        tags = re.split(r"[，、,]", val)
        return [t.strip() for t in tags if t.strip()]

    @staticmethod
    def _parse_relationships(text: str) -> list[CharacterRelationship]:
        """解析关系文本为 CharacterRelationship 列表。
        支持格式：
          - "角色A（恋人），角色B（敌人/复仇对象），角色C（闺蜜）"
          - "角色A-恋人，角色B-敌人"
          - "角色A: 恋人（两情相悦），角色B: 死对头"
        """
        if not text or not text.strip():
            return []
        rels: list[CharacterRelationship] = []

        # 先按中文逗号/英文逗号分割（但要避免把"（A，B）"内部分割了）
        # 简化：用正则匹配 "角色名（关系类型）" 或 "角色名：关系类型"
        pattern = re.compile(
            r"([^\s,，、:：（）\(\)]+?)\s*[：:]\s*([^,，、]+)|"           # 角色名：关系描述
            r"([^\s,，、:：（）\(\)]+?)\s*[（\(]\s*([^）\)]+)\s*[）\)]|"  # 角色名（关系类型）
            r"([^\s,，、:：（）\(\)]+?)\s*[-—]\s*([^,，、]+)"              # 角色名-关系类型
        )
        matches = pattern.findall(text)

        if matches:
            for m in matches:
                # 匹配模式1: name: desc
                if m[0]:
                    target = m[0].strip()
                    desc = m[1].strip()
                    rel_type, rel_desc = _split_rel_type_desc(desc)
                    rels.append(CharacterRelationship(
                        target_name=target,
                        relation_type=rel_type,
                        description=rel_desc,
                    ))
                # 匹配模式2: name（type）
                elif m[2]:
                    target = m[2].strip()
                    desc = m[3].strip()
                    rel_type, rel_desc = _split_rel_type_desc(desc)
                    rels.append(CharacterRelationship(
                        target_name=target,
                        relation_type=rel_type,
                        description=rel_desc,
                    ))
                # 匹配模式3: name-type
                elif m[4]:
                    target = m[4].strip()
                    desc = m[5].strip()
                    rel_type, rel_desc = _split_rel_type_desc(desc)
                    rels.append(CharacterRelationship(
                        target_name=target,
                        relation_type=rel_type,
                        description=rel_desc,
                    ))
        else:
            # 回退：简单按逗号分割
            parts = re.split(r"[，,]", text)
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                # 尝试拆分 "角色名-关系" 或 "角色名 关系"
                match = re.match(r"(.+?)[-—\s]+(.+)", part)
                if match:
                    target = match.group(1).strip()
                    desc = match.group(2).strip()
                    rel_type, rel_desc = _split_rel_type_desc(desc)
                    rels.append(CharacterRelationship(
                        target_name=target,
                        relation_type=rel_type,
                        description=rel_desc,
                    ))
                else:
                    rels.append(CharacterRelationship(
                        target_name=part,
                        relation_type="相关",
                    ))

        return rels


# =============================================================================
# 便捷入口函数
# =============================================================================

def parse_novel_text(path: Path | str) -> list[Chapter]:
    """解析任意小说文本文件，返回章节列表"""
    return NovelTextParser().parse_file(path)


def parse_notel_project(project_dir: Path | str) -> ParsedNovel:
    """解析 notel 标准项目目录"""
    return NotelProjectParser(project_dir).parse()
