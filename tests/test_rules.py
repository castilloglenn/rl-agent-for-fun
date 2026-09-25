"""Game rules files (roadmap step 4g, decision 013)."""

import json

import pytest

from src.config import get_maze_car_config
from src.envs.maze_car.env import MazeCarEnv
from src.replay.recorder import ReplayRecorder, human_driver
from src.replay.replayer import Replayer, replay_rules
from src.sim.components import Score
from src.sim.factories import create_game
from src.sim.resources import RoundState
from src.sim.rules import RULES_DIR, Rules, RulesError, load_rules

GAS = (False, False, True, False, False)


def _config():
    config = get_maze_car_config()
    config.show_gui = False
    return config


def test_standard_rules_are_todays_values():
    rules = load_rules("standard")
    assert (rules.round_seconds, rules.rounds) == (60, 1)
    assert (rules.scoring.distance_step, rules.scoring.checkpoint) == (10, 100)


@pytest.mark.parametrize("name, seconds", [("sprint", 30), ("marathon", 120)])
def test_example_rules(name, seconds):
    world, _ = create_game(_config(), rules=load_rules(name))
    assert world.resource(RoundState).steps_total == seconds * 120


def test_round_trip_matches_the_files():
    for path in RULES_DIR.glob("*.json"):
        rules = load_rules(str(path))
        assert rules.to_dict() == json.loads(path.read_text())
        assert Rules.from_dict(rules.to_dict()) == rules


@pytest.mark.parametrize(
    "change, message",
    [
        ({"format": 2}, "unsupported rules format"),
        ({"round_seconds": 0}, "round_seconds must be positive"),
        ({"rounds": 0}, "rounds must be"),
        ({"rounds": 1.5}, "rounds must be"),
        ({"scoring": {"distance_step": 0}}, "distance_step must be positive"),
    ],
)
def test_invalid_rules_are_rejected(change, message):
    data = {**load_rules("standard").to_dict(), **change}
    with pytest.raises(RulesError, match=message):
        Rules.from_dict(data)


def test_a_round_length_override_renames_the_rules():
    rules = load_rules("standard").with_round_seconds(90)
    assert rules.name == "standard-90s"
    assert rules.round_seconds == 90
    assert rules.scoring == load_rules("standard").scoring


def test_scoring_comes_from_the_rules():
    double = Rules.from_dict(
        {
            **load_rules("standard").to_dict(),
            "name": "double",
            "scoring": {"distance_step": 5, "checkpoint": 200},
        }
    )
    totals = []
    for rules in (load_rules("standard"), double):
        env = MazeCarEnv(_config(), rules=rules)
        env.reset(seed=1)
        for _ in range(150):
            env.step(GAS)
        totals.append(env.world.component(env.car, Score).distance_points)
    assert totals[1] == pytest.approx(2 * totals[0], abs=1)


def test_env_takes_rules_by_name():
    env = MazeCarEnv(_config(), rules="sprint")
    assert env.world.resource(Rules).name == "sprint"


def test_replays_embed_and_use_their_rules():
    recorder = ReplayRecorder({"1": human_driver("zen")})
    env = MazeCarEnv(_config(), rules="sprint", recorder=recorder)
    env.reset(seed=2)
    for i in range(400):
        env.step_world((i % 100 < 30, False, True, False, False))
    env.finish_recording()
    assert recorder.replay.header["rules"] == load_rules("sprint").to_dict()

    replayer = Replayer(recorder.replay)  # today's config says "standard"
    assert replayer.env.world.resource(Rules).name == "sprint"
    assert replayer.run().ok


def test_replays_from_before_rules_files_still_load():
    old_header = {
        "config": {
            "round": {"seconds": 60.0},
            "game": {"rounds": 1, "seed": 0},
            "rewards": {"distance_step": 10.0, "checkpoint": 100},
        }
    }
    rules = replay_rules(old_header)
    assert (rules.round_seconds, rules.rounds) == (60, 1)
    assert rules.scoring == load_rules("standard").scoring
