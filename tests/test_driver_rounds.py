"""A driver's rounds as recordings, for imitating the heuristic (7c15).
Recordings here go to tmp_path, never recordings/.
"""

import pytest

from src.config import get_maze_car_config
from src.drivers.registry import DriverError
from src.experiments.datasets import build_dataset, load_dataset_spec
from src.experiments.driver_rounds import player_of, record_rounds
from src.replay.format import read_replay
from tests.test_training import SHORT


def test_heuristic_rounds_become_a_dataset(tmp_path):
    config = get_maze_car_config()
    config.stage = "basics"  # box, pillars, s_curve, arena: in turn
    heard = []
    saved = record_rounds(
        "heuristic",
        config,
        rounds=4,
        rules=SHORT,
        root=tmp_path,
        on_round=lambda i, stage, result: heard.append(stage),
    )
    assert heard == ["box", "pillars", "s_curve", "arena"]
    assert len(saved) == 4
    assert all(p.parent == tmp_path / "Heuristic" for p in saved)
    headers = [read_replay(p).header for p in saved]
    assert sorted(h["stage"]["name"] for h in headers) == sorted(heard)
    assert all(h["slots"]["1"]["id"] == "heuristic" for h in headers)
    # The built-in dataset reads them: samples to clone.
    spec = load_dataset_spec("heuristic")
    assert spec.player == "Heuristic"
    dataset = build_dataset(spec, action_repeat=4, root=tmp_path)
    assert len(dataset.rounds) == 4 and dataset.samples > 0


def test_the_keyboard_cant_be_recorded_headless(tmp_path):
    with pytest.raises(DriverError):
        record_rounds("keyboard", get_maze_car_config(), 1, root=tmp_path)


def test_player_names():
    assert player_of("heuristic") == "Heuristic"
    assert player_of("agent:rookie@d0100k") == "Rookie_d0100k"


def test_a_curriculum_or_an_unknown_stage_is_refused(tmp_path):
    """A curriculum's hard levels would teach a clone to get stuck: it
    says so, and names the first level's mix to use instead.
    """
    from src.experiments.driver_rounds import RecordError

    config = get_maze_car_config()
    config.stage = "skills"
    with pytest.raises(RecordError, match="skill_training_easy"):
        record_rounds("heuristic", config, 1, root=tmp_path)
    config.stage = "lava"
    with pytest.raises(RecordError, match="no stage or mix named 'lava'"):
        record_rounds("heuristic", config, 1, root=tmp_path)


def test_the_record_action_offers_stages_and_mixes_only():
    from src.control.actions import ACTIONS

    action = next(a for a in ACTIONS if a.name == "Record a driver's rounds")
    stage = next(f for f in action.fields if f.name == "Stage")
    labels = [getattr(o, "label", o) for o in stage.options()]
    assert "mix: skill_training_easy" in labels
    assert not any(str(label).startswith("curriculum:") for label in labels)
