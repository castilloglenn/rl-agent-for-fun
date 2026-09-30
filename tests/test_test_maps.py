"""Training on a test map warns (roadmap 7d3b)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from src.utils.test_maps import skills_on, warning  # noqa: E402


def test_which_skills_a_map_tests():
    assert skills_on("skill_pillars") == ["Obstacles"]
    assert skills_on("box") == ["Braking", "Open field"]
    assert skills_on("arena") == []


def test_only_test_maps_warn():
    assert warning("box") is None  # the map to train on
    assert warning("arena") is None  # no suite plays there
    text = warning("skill_corridor")
    assert text == (
        "skill_corridor is a test map: its Corridor score would measure "
        "memory, not skill"
    )


def test_the_training_tab_warns_before_training_on_one(tmp_path):
    from tests.test_training_tab import _plan, _values

    plan = _plan(_values(Stage="skill_pillars"), runs_dir=tmp_path)
    assert any("skill_pillars is a test map" in w for w in plan.warnings)
    assert not plan.blockers  # a warning: it still starts
    plan = _plan(_values(Stage="box"), runs_dir=tmp_path)
    assert not any("test map" in w for w in plan.warnings)
