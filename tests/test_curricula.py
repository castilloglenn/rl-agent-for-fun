"""Curricula (7f5): levels of maps, moving up on goals judged on the
training maps, earlier maps kept in the mix. Everything here is in
tmp_path.
"""

import csv
import json

import pytest

import src.experiments.training as training
from src.agents.model import load_model_spec
from src.agents.store import create_agent
from src.config import get_maze_car_config
from src.utils import curricula
from src.utils.curricula import (
    Curriculum,
    CurriculumError,
    CurriculumState,
    Teacher,
)
from tests.test_training import SHORT, TINY

TWO = Curriculum.from_dict(
    {
        "format": 1,
        "name": "two",
        "earlier_share": 0.25,
        "window": 2,
        "levels": [
            {"mix": "box", "goal": 1.0, "min_decisions": 0,
             "max_decisions": 256},
            {"mix": "pillars", "goal": 1.0, "min_decisions": 0},
        ],
    }
)


def _teacher(level_maps, heuristic=None, window=2, **level):
    spec = Curriculum.from_dict(
        {
            "format": 1, "name": "t", "window": window,
            "levels": [
                {"mix": "box", "goal": 1.0, "min_decisions": 0, **level},
                {"mix": "box"},
            ],
        }
    )
    return Teacher(spec, level_maps, heuristic or {"a": 6.0, "b": 6.0})


def test_the_built_in_curriculum_goes_easy_to_hard():
    skills = curricula.load_curriculum("skills")
    assert [level.mix for level in skills.levels] == [
        "skill_training_easy", "skill_training",
    ]
    assert skills.all_maps() == [
        "box", "arena", "course_small_easy", "course_large", "course_small",
    ]
    assert curricula.is_curriculum("skills")


@pytest.mark.parametrize(
    "change, message",
    [
        ({"levels": []}, "list of levels"),
        ({"levels": [{"goal": 1}]}, "names a mix"),
        ({"earlier_share": 1.0}, "earlier_share"),
        ({"window": 1}, "window"),
    ],
)
def test_bad_curricula_are_refused(change, message):
    data = {**TWO.to_dict(), **change}
    with pytest.raises(CurriculumError, match=message):
        Curriculum.from_dict(data)


def test_maps_take_turns_by_share_earlier_ones_kept():
    teacher = _teacher([["a", "b"], ["b", "c", "d"]])
    picks = []
    for _ in range(40):
        stage = teacher.next_map()
        teacher.started(stage)
        picks.append(stage)
        teacher.played(stage, 1, 1.0)
    assert picks.count("a") == picks.count("b") == 20  # level 1: even
    teacher.state = CurriculumState(level=1)
    assert teacher.shares() == pytest.approx(
        {"b": 0.25, "c": 0.25, "d": 0.25, "a": 0.25}
    )  # a: only level 1 had it, a quarter of the episodes
    picks = []
    for _ in range(100):
        stage = teacher.next_map()
        teacher.started(stage)
        picks.append(stage)
        teacher.played(stage, 1, 1.0)
    assert {m: picks.count(m) for m in "abcd"} == {
        "a": 25, "b": 25, "c": 25, "d": 25,
    }


def test_games_starting_together_get_different_maps():
    """Step 8: counted at the start, four rounds starting before any ends
    each take the map furthest behind after the ones before them.
    """
    teacher = _teacher([["a", "b", "c", "d"]])
    picks = []
    for _ in range(4):
        stage = teacher.next_map()
        teacher.started(stage)
        picks.append(stage)
    assert sorted(picks) == ["a", "b", "c", "d"]


def test_it_moves_up_on_the_goal_once_leveled_off():
    teacher = _teacher([["a", "b"], ["c"]], min_decisions=100)
    for rate in (3, 3, 7, 7):  # a, b: under the heuristic's 6, then over
        for stage in "ab":
            teacher.played(stage, rate, 1.0)
    assert teacher.check(50) is None  # too soon (min 100)
    assert teacher.check(100) is None  # beat it, but still improving
    for stage in "ab":
        teacher.played(stage, 7, 1.0)
        teacher.played(stage, 7, 1.0)
    assert teacher.progress() == pytest.approx({"a": 7 / 6, "b": 7 / 6})
    assert teacher.check(120) == "goal"  # beat it, and leveled off
    assert teacher.state.level == 1 and teacher.state.started == 120
    assert teacher.check(10**9) is None  # the last level: it stays


def test_a_cap_moves_it_up_anyway():
    teacher = _teacher([["a"], ["b"]], max_decisions=500)
    teacher.played("a", 0, 1.0)  # nowhere near the heuristic
    assert teacher.check(499) is None
    assert teacher.check(500) == "cap"


def test_a_map_the_heuristic_cant_do_counts_a_floor():
    teacher = _teacher([["a"], ["b"]], heuristic={"a": 0.0})
    for _ in range(2):
        teacher.played("a", 1, 1.0)
    assert teacher.progress() == {"a": 1.0 / curricula.FLOOR}


# Training with one


def _train_on(tmp_path, monkeypatch, curriculum=TWO, **kwargs):
    monkeypatch.setattr(training, "is_curriculum", lambda name: True)
    monkeypatch.setattr(training, "load_curriculum", lambda name: curriculum)
    monkeypatch.setattr(
        Curriculum, "all_maps", lambda self, root=None: ["box", "pillars"]
    )
    monkeypatch.setattr(
        Curriculum,
        "level_maps",
        lambda self, root=None: [["box"], ["pillars"]],
    )
    root = tmp_path / "agents"
    if not (root / "pupil").exists():
        create_agent("pupil", load_model_spec("small"), root=root)
    config = get_maze_car_config()
    config.stage = "two"
    return training.train_agent(
        "pupil", TINY, config, rules=SHORT, runs_dir=tmp_path / "runs",
        agents_root=root, **kwargs,
    )


def _rows(path):
    with open(path) as file:
        return list(csv.DictReader(file))


def test_a_training_moves_up_its_curriculum(tmp_path, monkeypatch):
    summary = _train_on(tmp_path, monkeypatch)
    learning = _rows(summary.folder / "learning.csv")
    levels = [row["level"] for row in learning]
    assert levels[0] == "1" and levels[-1] == "2"  # capped at 256
    metrics = _rows(summary.folder / "metrics.csv")
    first = metrics[0]["stage"]
    assert first == "box"
    later = [row["stage"] for row in metrics[-4:]]
    assert "pillars" in later  # level 2's map
    history = [
        json.loads(line)
        for line in (tmp_path / "agents" / "pupil" / "history.jsonl")
        .read_text().splitlines()
    ]
    (up,) = [e for e in history if e["event"] == "level_up"]
    assert up["level"] == 2 and up["why"] == "cap"
    config = json.loads((summary.folder / "config.json").read_text())
    assert config["curriculum"]["spec"]["name"] == "two"
    assert set(config["curriculum"]["heuristic"]) == {"box", "pillars"}
    baselines = tmp_path / "agents" / "baselines" / "maps.json"
    assert baselines.exists()  # the heuristic's rates, cached


def test_a_new_phase_starts_where_the_last_left_off(tmp_path, monkeypatch):
    _train_on(tmp_path, monkeypatch)
    second = _train_on(tmp_path, monkeypatch)
    learning = _rows(second.folder / "learning.csv")
    assert learning[0]["level"] == "2"


def test_a_curriculum_run_resumes_the_same_twice(tmp_path, monkeypatch):
    """Step 8: a resume starts fresh rounds; its level and counts carry
    over, so resuming the same state twice gives the same run.
    """
    from tests.test_resume import _same_run, _stop_at

    resumed = []
    for where in ("a", "b"):
        stopped = _train_on(
            tmp_path / where, monkeypatch, on_update=_stop_at(2)
        )
        resumed.append(
            training.resume_training(
                stopped.folder, agents_root=tmp_path / where / "agents"
            )
        )
    _same_run(resumed[0].folder, resumed[1].folder)


# Seeing it


def test_the_runs_tab_names_the_level_and_marks_level_ups(
    tmp_path, monkeypatch
):
    from src.control import charts
    from src.control.runs import RunData, run_place

    summary = _train_on(tmp_path, monkeypatch)
    data = RunData(summary.folder, tmp_path / "agents")
    assert run_place(data.config) == "curriculum two (2 levels)"
    assert "curriculum two · level 2 of 2" in data.description()
    marks = data.main_chart().series[-1]
    assert marks.style == charts.MARKS and len(marks.points) == 1
    assert marks.label == "level 2"
    second = data.second_chart("Agent reward")
    assert second.series[-1].style == charts.MARKS


def test_marks_dont_set_the_axes_or_count_as_data():
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from src.control import charts

    marks = charts.Series("level 2", [(500.0, 2.0)], (1, 2, 3), charts.MARKS)
    assert charts.Chart("T", [marks], "{}").empty
    line = charts.Series("s", [(0.0, 10.0), (1000.0, 20.0)], (9, 9, 9))
    pygame.init()
    surface = pygame.Surface((400, 200))
    plot = charts.draw_chart(
        surface, surface.get_rect(), charts.Chart("T", [line, marks], "{}")
    )
    _, top = plot.to_screen(0, 20.0)
    assert top >= plot.area.y  # y = 2 didn't stretch the axis


def test_the_stage_dropdown_the_plan_and_the_warning_know_curricula():
    from src.control import actions
    from src.control.training_plan import RL, make_plan
    from src.utils import test_maps

    labels = [getattr(o, "label", o) for o in actions._stages_and_mixes()]
    assert "curriculum: skills" in labels
    plan = make_plan(
        {"Mode": RL, "Agent": "a", "Seed": "0", "Trainer": "default",
         "Stage": "skills", "Rules": "standard", "Round seconds": "",
         "Reward profile": "default"},
        ["a"], {},
    )
    assert "curriculum skills (skill_training_easy, then skill_training" in (
        plan.steps[0].text
    )
    assert test_maps.warning("skills") is None  # no skill_ test map
