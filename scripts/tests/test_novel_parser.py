"""
novel_parser 测试 — 章节解析（多种格式、边界情况）。
"""
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from novel_parser import NovelTextParser, NotelProjectParser, Chapter, ParsedNovel


# =============================================================================
# NovelTextParser
# =============================================================================

class TestNovelTextParser:
    def setup_method(self):
        self.parser = NovelTextParser()

    # ---- notel 格式 ----
    def test_notel_format(self):
        text = "###1. 第一章\n\n这是第一章的内容。\n\n###2. 第二章标题\n\n这是第二章。"
        chapters = self.parser.parse_text(text)
        assert len(chapters) == 2
        assert chapters[0].number == 1
        assert chapters[0].title == "第一章"
        assert "第一章的内容" in chapters[0].content
        assert chapters[1].number == 2
        assert chapters[1].title == "第二章标题"

    # ---- 中文格式 ----
    def test_zh_chapter_format(self):
        text = "第1章：苏醒\n\n她从黑暗中醒来。\n\n第2章 试探\n\n她走向门口。"
        chapters = self.parser.parse_text(text)
        assert len(chapters) == 2
        assert chapters[0].number == 1
        assert chapters[0].title == "苏醒"

    def test_zh_chapter_no_colon(self):
        text = "第1章 苏醒\n\n内容。\n\n第2章\n\n内容。"
        chapters = self.parser.parse_text(text)
        assert len(chapters) >= 1

    # ---- 英文格式 ----
    def test_en_chapter_format(self):
        text = "Chapter 1: Awakening\n\nShe opened her eyes.\n\nChapter 2: The Door\n\nShe walked forward."
        chapters = self.parser.parse_text(text)
        assert len(chapters) == 2
        assert chapters[0].title == "Awakening"

    # ---- 无分隔符 ----
    def test_no_delimiters_single_chapter(self):
        text = "这是一段没有任何章节标记的文本。"
        chapters = self.parser.parse_text(text)
        assert len(chapters) == 1
        assert chapters[0].number == 1

    def test_empty_text_raises(self):
        with pytest.raises(ValueError, match="输入文本"):
            self.parser.parse_text("")
        with pytest.raises(ValueError, match="输入文本"):
            self.parser.parse_text("   \n\n  ")

    # ---- 文件 I/O ----
    def test_parse_file_notel_format(self):
        content = "###1. 标题一\n\n内容一。\n\n###2. 标题二\n\n内容二。\n\n###3. 标题三\n\n内容三。"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(content)
            path = Path(f.name)
        try:
            chapters = self.parser.parse_file(path)
            assert len(chapters) == 3
        finally:
            path.unlink()

    def test_parse_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            self.parser.parse_file(Path("/nonexistent/file.txt"))

    def test_parse_file_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("")
            path = Path(f.name)
        try:
            with pytest.raises(ValueError, match="文件为空"):
                self.parser.parse_file(path)
        finally:
            path.unlink()

    # ---- 边界 ----
    def test_large_chapter_numbers_ignored(self):
        text = "###999999. 超大纲\n\n内容。"
        chapters = self.parser.parse_text(text)
        # number > 100000 会被跳过
        assert len(chapters) <= 1

    def test_very_long_title_truncated(self):
        long_title = "A" * 300
        text = f"###1. {long_title}\n\n内容。"
        chapters = self.parser.parse_text(text)
        assert len(chapters) == 1
        assert len(chapters[0].title or "") <= 200

    def test_empty_chapter_skipped(self):
        text = "###1. 空章\n\n\n\n###2. 有内容\n\n正文。"
        chapters = self.parser.parse_text(text)
        assert len(chapters) == 1
        assert chapters[0].title == "有内容"


# =============================================================================
# ParsedNovel
# =============================================================================

class TestParsedNovel:
    def test_get_chapter(self):
        novel = ParsedNovel(title="测试", chapters=[
            Chapter(number=1, title="一"), Chapter(number=3, title="三")
        ])
        assert novel.get_chapter(1).title == "一"
        assert novel.get_chapter(3).title == "三"
        assert novel.get_chapter(2) is None

    def test_get_outline(self):
        from novel_parser import ChapterOutline
        novel = ParsedNovel(title="测试", outlines=[
            ChapterOutline(number=1, title="一", mood_start="平静", mood_end="紧张")
        ])
        ol = novel.get_outline(1)
        assert ol is not None
        assert ol.mood_start == "平静"
        assert novel.get_outline(99) is None


# =============================================================================
# NotelProjectParser (仅测试设定解析逻辑，不依赖实际文件)
# =============================================================================

class TestNotelProjectParser:
    def test_extract_value(self):
        assert NotelProjectParser._extract_value("主事件：她醒来") == "她醒来"
        assert NotelProjectParser._extract_value("key: value") == "value"
        assert NotelProjectParser._extract_value("no colon") == "no colon"

    def test_extract_tags(self):
        tags = NotelProjectParser._extract_tags("别名：小明，小亮，阿亮")
        assert "小明" in tags
        assert len(tags) >= 2

    def test_extract_tags_english_comma(self):
        tags = NotelProjectParser._extract_tags("别名：a, b, c")
        assert tags == ["a", "b", "c"]

    # 设定解析 — 只测方法存在，不测文件依赖
    def test_parse_empty_setting(self):
        parser = NotelProjectParser.__new__(NotelProjectParser)
        chars = parser._parse_setting("")
        assert chars == []

    def test_parse_setting_with_characters(self):
        parser = NotelProjectParser.__new__(NotelProjectParser)
        text = """## 人设
### 林婉
- 描述：穿书女主，性格冷静
- 声音：低沉短句
- 原型：清醒女主
- 别名：林小姐

### 顾夜
- 描述：病娇男主
"""
        chars = parser._parse_setting(text)
        assert len(chars) >= 2
        names = [c.name for c in chars]
        assert "林婉" in names
        assert "顾夜" in names

    def test_parse_setting_skips_non_character(self):
        parser = NotelProjectParser.__new__(NotelProjectParser)
        text = """## 人设
### 世界观设定
- 描述：现代都市

### 林婉
- 描述：主角
"""
        chars = parser._parse_setting(text)
        names = [c.name for c in chars]
        assert "林婉" in names
        assert "世界观设定" not in names

    def test_parse_outline_section(self):
        from novel_parser import ChapterOutline
        parser = NotelProjectParser.__new__(NotelProjectParser)
        text = """主事件：林婉醒来发现穿越
情绪：平静→恐慌
钩子：她是谁？
动静：动
对话密度：高
子事件：睁眼->环顾->确认"""
        ol = ChapterOutline(number=1)
        ol = parser._parse_outline_section(text, ol)
        assert ol.main_event == "林婉醒来发现穿越"
        assert ol.emotion_arc == "平静→恐慌"
        assert ol.mood_start == "平静"
        assert ol.mood_end == "恐慌"
        assert ol.hook == "她是谁？"
        assert ol.pacing == "动"
        assert ol.dialogue_density == "高"
