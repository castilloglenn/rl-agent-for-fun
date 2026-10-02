"""Map mixes (roadmap 7d5a): a named file listing stages, played in turn
by one training phase. Files here are in tmp_path, except the built-in
basics mix, which is only read.
"""

import json

import pytest

from src.utils import mixes, named_files, test_maps


def _repo(tmp_path, mix_stages, name="practice"):
    for stage in ("box", "pillars", "skill_gaps"):
        folder = tmp_path / "stages"
        folder.mkdir(exist_ok=True)
        (folder / f"{stage}.json").write_text("{}")
    folder = tmp_path / "user" / "mixes"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(
        json.dumps({"format": 1, "name": name, "stages": mix_stages})
    )
    return tmp_path


def test_the_built_in_mix_loads():
    mix = mixes.load_mix("basics")
    assert mix.stages == ("box", "pillars", "s_curve", "arena")
    assert mixes.is_mix("basics") and not mixes.is_mix("box")
    assert mixes.stages_of("box") == ["box"]
    assert named_files.is_built_in("mixes", "basics")


def test_a_mix_of_yours(tmp_path):
    root = _repo(tmp_path, ["box", "pillars"])
    assert mixes.stages_of("practice", root) == ["box", "pillars"]


@pytest.mark.parametrize(
    "data, message",
    [
        ({"format": 2, "name": "m", "stages": ["box"]}, "unsupported"),
        ({"format": 1, "name": "m", "stages": []}, "a list of stages"),
        ({"format": 1, "name": "m", "stages": "box"}, "a list of stages"),
        ({"format": 1, "name": "m", "stages": ["box", 3]}, "stage's name"),
    ],
)
def test_bad_mixes_are_rejected(data, message):
    with pytest.raises(mixes.MixError, match=message):
        mixes.Mix.from_dict(data)


def test_a_mix_names_only_real_stages(tmp_path):
    root = _repo(tmp_path, ["box", "lava"])
    with pytest.raises(mixes.MixError, match="no stage 'lava'"):
        mixes.load_mix("practice", root)


def test_a_stage_of_the_same_name_wins(tmp_path):
    root = _repo(tmp_path, ["box"], name="pillars")
    assert not mixes.is_mix("pillars", root)
    assert mixes.stages_of("pillars", root) == ["pillars"]


def test_the_test_map_warning_covers_every_map_in_a_mix():
    assert test_maps.warning("basics") is None  # no skill_ map in it


def test_a_mix_with_a_test_map_warns(tmp_path, monkeypatch):
    root = _repo(tmp_path, ["box", "skill_gaps"])
    monkeypatch.setattr(
        test_maps, "skills_on",
        lambda stage, root: ["Threading"] if stage == "skill_gaps" else [],
    )
    text = test_maps.warning("practice", root)
    assert text.startswith("mix practice: skill_gaps is a test map")


def test_the_skill_training_mix_has_no_test_map():
    """7d5b: every skill practiced, none on its skill_ test map."""
    mix = mixes.load_mix("skill_training")
    assert mix.stages == ("box", "arena", "course_small", "course_large")
    assert not any(s.startswith("skill_") for s in mix.stages)
    assert test_maps.warning("skill_training") is None


def test_the_easy_mix_is_the_first_level():
    """7f2: skill_training_easy swaps in the easy course, no test map."""
    easy = mixes.load_mix("skill_training_easy").stages
    hard = mixes.load_mix("skill_training").stages
    assert easy == tuple(
        "course_small_easy" if s == "course_small" else s for s in hard
    )
    assert test_maps.warning("skill_training_easy") is None


def test_the_navigators_lessons_have_no_test_map():
    """7f12: where the route bends away from the compass, no skill_ map."""
    stages = mixes.load_mix("route_lessons").stages
    assert "s_curve" in stages and "course_small" in stages
    assert not any(s.startswith("skill_") for s in stages)
    assert test_maps.warning("route_lessons") is None
