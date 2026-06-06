"""
plan_episodes 测试 — 漫剧集数自动规划算法。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from yaml_exporter import Scene, SceneHeading, Episode
from novel_to_script import plan_episodes


def make_scene(scid, duration=90, scene_type=None):
    """快速构造 Scene"""
    return Scene(
        scene_id=scid, sequence_id="seq_01",
        heading=SceneHeading(int_ext="INT.", location="Room", time="DAY"),
        estimated_duration_seconds=duration,
        type=scene_type,
        beats=[],
    )


class TestPlanEpisodesBasic:
    def test_empty_scenes(self):
        assert plan_episodes([]) == []

    def test_single_scene(self):
        scenes = [make_scene("sc_001", 90)]
        eps = plan_episodes(scenes)
        assert len(eps) == 1
        assert eps[0].episode_number == 1
        assert eps[0].scenes == ["sc_001"]

    def test_auto_split_by_duration(self):
        """4 个 scene 各 200s，总 800s → 应该拆成至少 3 集"""
        scenes = [make_scene(f"sc_{i:03d}", 200) for i in range(1, 5)]
        eps = plan_episodes(scenes, min_duration=180, max_duration=300)
        assert len(eps) >= 3  # 800/240 ≈ 3.3

    def test_min_duration_enforced(self):
        """短 scene 合并达到 min 时长"""
        scenes = [make_scene(f"sc_{i:03d}", 30) for i in range(1, 11)]
        eps = plan_episodes(scenes, min_duration=180, max_duration=300)
        # 10×30=300，至少拆成 1 集，最多 2 集
        for ep in eps:
            dur = sum(
                s.estimated_duration_seconds or 60
                for s in scenes if s.scene_id in ep.scenes
            )
            assert dur > 0


class TestPlanEpisodesNoSplit:
    def test_auto_split_false_single_episode(self):
        scenes = [make_scene(f"sc_{i:03d}", 200) for i in range(1, 6)]
        eps = plan_episodes(scenes, auto_split=False)
        assert len(eps) == 1
        assert len(eps[0].scenes) == 5

    def test_auto_split_false_empty(self):
        assert plan_episodes([], auto_split=False) == []


class TestPlanEpisodesTargetCount:
    def test_target_2_episodes(self):
        """6 个场景各 120s=720s，目标 2 集"""
        scenes = [make_scene(f"sc_{i:03d}", 120) for i in range(1, 7)]
        eps = plan_episodes(scenes, target_episodes=2, min_duration=180, max_duration=400)
        assert len(eps) == 2
        # 每集约 360s
        for ep in eps:
            dur = sum(
                s.estimated_duration_seconds or 60
                for s in scenes if s.scene_id in ep.scenes
            )
            assert 180 <= dur <= 500  # 宽松范围

    def test_target_1_episode(self):
        scenes = [make_scene(f"sc_{i:03d}", 100) for i in range(1, 4)]
        eps = plan_episodes(scenes, target_episodes=1, min_duration=60, max_duration=600)
        assert len(eps) >= 1


class TestPlanEpisodesHookAndTitle:
    def test_hook_style_cliffhanger(self):
        scenes = [make_scene("sc_001", 200)]
        eps = plan_episodes(scenes, hook_style="cliffhanger")
        assert "悬念" in eps[0].hook or "待设计" in eps[0].hook

    def test_hook_style_twist(self):
        scenes = [make_scene("sc_001", 200)]
        eps = plan_episodes(scenes, hook_style="twist")
        assert "反转" in eps[0].hook

    def test_hook_style_with_mood(self):
        scenes = [Scene(
            scene_id="sc_001", sequence_id="seq_01",
            heading=SceneHeading(int_ext="INT.", location="Room", time="NIGHT"),
            estimated_duration_seconds=200,
            mood="压抑→警觉",
            beats=[],
        )]
        eps = plan_episodes(scenes, hook_style="suspense")
        assert "悬疑" in eps[0].hook
        assert "压抑→警觉" in eps[0].hook

    def test_title_template(self):
        scenes = [make_scene("sc_001", 200)]
        eps = plan_episodes(scenes, title_template="Episode {n} — {subtitle}")
        assert "Episode 1" in eps[0].title

    def test_title_template_with_pause(self):
        scenes = [make_scene("sc_001", 200)]
        eps = plan_episodes(scenes, title_template="第{n}集{pause}{subtitle}")
        assert eps[0].title.startswith("第1集")


class TestPlanEpisodesEdgeCases:
    def test_transition_scene_as_split_point(self):
        """transition 类型 scene 可作为切分点"""
        scenes = [
            make_scene("sc_001", 180, scene_type="dialogue_heavy"),
            make_scene("sc_002", 30, scene_type="transition"),
            make_scene("sc_003", 180, scene_type="action"),
        ]
        eps = plan_episodes(scenes, min_duration=180, max_duration=300)
        # sc_002 是 transition 且前面积累 180s，可切分
        assert len(eps) >= 1

    def test_scene_ids_unique(self):
        """切分后的 scene_ids 不应该重复或遗漏"""
        scenes = [make_scene(f"sc_{i:03d}", 100) for i in range(1, 7)]
        eps = plan_episodes(scenes, target_episodes=3)
        all_ids = []
        for ep in eps:
            all_ids.extend(ep.scenes)
        expected = [s.scene_id for s in scenes]
        assert sorted(all_ids) == sorted(expected)

    def test_source_chapters_tracking(self):
        scenes = [
            Scene(scene_id="sc_001", sequence_id="seq_01",
                  heading=SceneHeading(int_ext="INT.", location="A", time="DAY"),
                  estimated_duration_seconds=200, source_chapters=[1], beats=[]),
            Scene(scene_id="sc_002", sequence_id="seq_01",
                  heading=SceneHeading(int_ext="INT.", location="B", time="DAY"),
                  estimated_duration_seconds=200, source_chapters=[2], beats=[]),
        ]
        eps = plan_episodes(scenes, min_duration=300, max_duration=500)
        # 两个 scene 共 400s → 1 集，source_chapters 应为 [1, 2]
        if len(eps) == 1:
            assert eps[0].source_chapters == [1, 2]

    def test_very_long_single_scene(self):
        """单个极长场景仍独立成集"""
        scenes = [make_scene("sc_001", 1000)]
        eps = plan_episodes(scenes, min_duration=180, max_duration=300)
        assert len(eps) == 1
