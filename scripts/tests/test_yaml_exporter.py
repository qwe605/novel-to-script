"""
yaml_exporter 测试 — Pydantic 模型构造、序列化/反序列化、一致性校验。
"""
import pytest
import sys
from pathlib import Path

# 确保 scripts/ 在导入路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from yaml_exporter import (
    Beat, BeatExtensions, Character, Episode, ManjuExtensions, Metadata,
    Scene, SceneHeading, ScriptDocument, ScriptRoot, Sequence, validate_yaml_file,
)


# =============================================================================
# Helpers
# =============================================================================

def make_minimal_doc(script_type="manju", scenes=None, characters=None, sequences=None, episodes=None):
    """快速构造 ScriptDocument，默认有一切合法数据。"""
    actual_scenes = scenes or [
        Scene(
            scene_id="sc_001", sequence_id="seq_01",
            heading=SceneHeading(int_ext="INT.", location="房间", time="DAY"),
            beats=[Beat(beat_id="b_001", type="action", content="她推开门。")]
        ),
    ]
    return ScriptDocument(script=ScriptRoot(
        version="1.0",
        script_type=script_type,
        title="测试剧本",
        metadata=Metadata(
            total_scenes=len(actual_scenes),
            total_beats=sum(len(s.beats) for s in actual_scenes),
            total_episodes=len(episodes) if episodes else None,
        ),
        characters=characters or [Character(id="c1", name="主角")],
        sequences=sequences or [Sequence(id="seq_01", name="开端", scenes=[s.scene_id for s in actual_scenes])],
        episodes=episodes,
        scenes=actual_scenes,
    ))


def make_beat(bid, char=None, t="action"):
    return Beat(beat_id=bid, type=t, content=f"beat {bid}", character=char)


# =============================================================================
# Round-trip
# =============================================================================

class TestRoundTrip:
    def test_to_yaml_and_back(self):
        doc = make_minimal_doc()
        yaml_str = doc.to_yaml()
        doc2 = ScriptDocument.from_yaml(yaml_str)
        assert doc2.script.version == "1.0"
        assert doc2.script.title == "测试剧本"
        assert len(doc2.script.scenes) == 1

    def test_save_and_load(self, tmp_path):
        doc = make_minimal_doc()
        p = tmp_path / "test.yaml"
        doc.save(p)
        assert p.exists()
        doc2 = ScriptDocument.from_file(p)
        assert doc2.script.title == "测试剧本"

    def test_validate_yaml_file_ok(self, tmp_path):
        doc = make_minimal_doc()
        p = tmp_path / "valid.yaml"
        doc.save(p)
        ok, errors = validate_yaml_file(p)
        assert ok is True
        assert errors == []

    def test_validate_yaml_file_broken(self, tmp_path):
        p = tmp_path / "broken.yaml"
        p.write_text("script:\n  version: 99\n", encoding="utf-8")
        ok, errors = validate_yaml_file(p)
        assert ok is False
        assert len(errors) > 0


# =============================================================================
# Consistency checks
# =============================================================================

class TestValidateConsistency:
    def test_duplicate_scene_ids(self):
        s1 = Scene(scene_id="sc_001", sequence_id="seq_01", heading=SceneHeading(int_ext="INT.", location="A", time="DAY"),
                   beats=[make_beat("b1")])
        s2 = Scene(scene_id="sc_001", sequence_id="seq_01", heading=SceneHeading(int_ext="INT.", location="B", time="DAY"),
                   beats=[make_beat("b2")])
        doc = make_minimal_doc(scenes=[s1, s2], sequences=[
            Sequence(id="seq_01", name="开端", scenes=["sc_001", "sc_001"])
        ])
        errors = doc.validate_consistency()
        assert any("场景 ID 重复" in e for e in errors)

    def test_duplicate_beat_ids(self):
        s = Scene(scene_id="sc_001", sequence_id="seq_01",
                  heading=SceneHeading(int_ext="INT.", location="A", time="DAY"),
                  beats=[make_beat("b1"), make_beat("b1")])
        doc = make_minimal_doc(scenes=[s])
        errors = doc.validate_consistency()
        assert any("节拍 ID 重复" in e for e in errors)

    def test_invalid_sequence_ref(self):
        s = Scene(scene_id="sc_001", sequence_id="seq_GHOST",
                  heading=SceneHeading(int_ext="INT.", location="A", time="DAY"),
                  beats=[make_beat("b1")])
        doc = make_minimal_doc(scenes=[s])
        errors = doc.validate_consistency()
        assert any("不存在的序列" in e for e in errors)

    def test_invalid_character_in_beat(self):
        s = Scene(scene_id="sc_001", sequence_id="seq_01",
                  heading=SceneHeading(int_ext="INT.", location="A", time="DAY"),
                  beats=[make_beat("b1", char="ghost")])
        doc = make_minimal_doc(scenes=[s])
        errors = doc.validate_consistency()
        assert any("不存在的角色" in e for e in errors)

    def test_metadata_mismatch(self):
        doc = make_minimal_doc()
        doc.script.metadata.total_scenes = 999
        errors = doc.validate_consistency()
        assert any("total_scenes" in e for e in errors)

    def test_passing_checks(self):
        doc = make_minimal_doc()
        errors = doc.validate_consistency()
        assert errors == []

    def test_duplicate_episode_ids(self):
        s1 = Scene(scene_id="sc_001", sequence_id="seq_01",
                   heading=SceneHeading(int_ext="INT.", location="A", time="DAY"),
                   beats=[make_beat("b1")])
        s2 = Scene(scene_id="sc_002", sequence_id="seq_01",
                   heading=SceneHeading(int_ext="INT.", location="B", time="DAY"),
                   beats=[make_beat("b2")])
        ep1 = Episode(episode_id="ep_01", episode_number=1, scenes=["sc_001"],
                      target_duration_seconds=240)
        ep2 = Episode(episode_id="ep_01", episode_number=2, scenes=["sc_002"],
                      target_duration_seconds=240)
        doc = make_minimal_doc(scenes=[s1, s2], episodes=[ep1, ep2])
        errors = doc.validate_consistency()
        assert any("集 ID 重复" in e for e in errors)

    def test_episode_refs_invalid_scene(self):
        s = Scene(scene_id="sc_001", sequence_id="seq_01",
                  heading=SceneHeading(int_ext="INT.", location="A", time="DAY"),
                  beats=[make_beat("b1")])
        ep = Episode(episode_id="ep_01", episode_number=1, scenes=["sc_999"],
                     target_duration_seconds=240)
        doc = make_minimal_doc(scenes=[s], episodes=[ep])
        errors = doc.validate_consistency()
        assert any("不存在的场景" in e for e in errors)


# =============================================================================
# Model construction
# =============================================================================

class TestModelConstruction:
    def test_character_optional_fields(self):
        c = Character(id="lin_wan", name="林婉")
        assert c.aliases is None
        assert c.visual_tags is None

    def test_character_full(self):
        c = Character(id="gu_ye", name="顾夜", aliases=["顾总"], description="反派",
                      voice_tags=["低沉"], archetype="病娇", visual_tags=["黑发"])
        assert len(c.aliases) == 1
        assert c.visual_tags == ["黑发"]

    def test_beat_with_extensions(self):
        ext = BeatExtensions()
        from yaml_exporter import ManjuExtensions
        ext.manju = ManjuExtensions(shot="CLOSE-UP", subtitle_style="BUBBLE", duration_seconds=2.5)
        b = Beat(beat_id="b_001", type="dialogue", content="你好", character="c1", extensions=ext)
        assert b.extensions.manju.shot == "CLOSE-UP"
        assert b.extensions.manju.duration_seconds == 2.5

    def test_scene_heading(self):
        h = SceneHeading(int_ext="EXT.", location="街道 - 路口", time="DUSK")
        assert h.int_ext == "EXT."
        assert h.time == "DUSK"

    def test_episode_fields(self):
        ep = Episode(episode_id="ep_01", episode_number=1, title="第1集",
                     hook="悬念钩子", target_duration_seconds=240,
                     source_chapters=[1], scenes=["sc_001"],
                     cover_prompt="封面提示", opening_sfx="心跳声")
        assert ep.hook == "悬念钩子"
        assert ep.source_chapters == [1]
        assert ep.cover_prompt is not None

    def test_manju_visual_effect_enum(self):
        ext = ManjuExtensions(visual_effect="ZOOM_IN_EYE", effect_note="瞳孔放大")
        assert ext.visual_effect == "ZOOM_IN_EYE"
        # 非法值应触发校验
        with pytest.raises(Exception):
            ManjuExtensions(visual_effect="INVALID_EFFECT")

    def test_subtitle_style_enum(self):
        ext = ManjuExtensions(subtitle_style="DANMAKU")
        assert ext.subtitle_style == "DANMAKU"
        with pytest.raises(Exception):
            ManjuExtensions(subtitle_style="INVALID_STYLE")

    def test_metadata_with_episodes(self):
        m = Metadata(total_scenes=5, total_beats=30, total_episodes=3)
        assert m.total_episodes == 3

    def test_document_wrapper(self):
        doc = make_minimal_doc()
        assert doc.script.version == "1.0"
        assert doc.script.metadata.total_scenes == 1
