"""Training agents with PPO (roadmap 5a2)."""

import csv
import json

import pytest
import torch

from src.agents.driver import AgentDriver
from src.agents.model import load_model_spec
from src.agents.ppo import Rollout, advantages, update
from src.agents.store import create_agent, load_agent
from src.agents.trainer import (
    TRAINERS_DIR,
    TrainerError,
    TrainerSpec,
    load_trainer_spec,
)
from src.config import get_maze_car_config
from src.experiments.runs import format_runs, list_runs
from src.experiments.training import (
    LEARNING_COLUMNS,
    checkpoint_name,
    train_agent,
)
from src.replay.format import read_replay
from src.replay.replayer import Replayer
from src.sim.observation import OBSERVATION_NAMES
from src.sim.rules import load_rules

DEFAULT = load_trainer_spec("default")
TINY = TrainerSpec.from_dict(
    {
        **DEFAULT.to_dict(),
        "name": "tiny",
        "rollout": 128,
        "minibatch": 32,
        "epochs": 2,
        "total_decisions": 512,
        "checkpoint_every": 256,
        "evaluate": False,
    }
)
SHORT = load_rules("standard").with_round_seconds(3)  # 90 decisions


def _train(tmp_path, agent="pupil", trainer=TINY, **kwargs):
    root = tmp_path / "agents"
    if not (root / agent).exists():
        create_agent(agent, load_model_spec("small"), root=root)
    return train_agent(
        agent,
        trainer,
        get_maze_car_config(),
        rules=SHORT,
        runs_dir=tmp_path / "runs",
        agents_root=root,
        **kwargs,
    )


def _rows(path):
    with open(path) as file:
        return list(csv.DictReader(file))


# Trainer files


def test_trainer_files_load_and_round_trip():
    for path in TRAINERS_DIR.glob("*.json"):
        spec = load_trainer_spec(str(path))
        assert spec.to_dict() == json.loads(path.read_text()), path.name


@pytest.mark.parametrize(
    "change, message",
    [
        ({"format": 2}, "unsupported trainer format"),
        ({"algorithm": "dqn"}, "unknown algorithm"),
        ({"gamma": 1.5}, "gamma"),
        ({"gae_lambda": -0.1}, "gae_lambda"),
        ({"learning_rate": 0}, "learning_rate"),
        ({"entropy": -1}, "entropy"),
        ({"rollout": 0}, "rollout"),
        ({"minibatch": 4096}, "minibatch can't be larger"),
        ({"epochs": 2.5}, "epochs"),
        ({"learnin_rate": 0.1}, "unknown trainer keys: learnin_rate"),
    ],
)
def test_invalid_trainers_are_rejected(change, message):
    with pytest.raises(TrainerError, match=message):
        TrainerSpec.from_dict({**DEFAULT.to_dict(), **change})


def test_missing_trainer_keys_and_files():
    data = DEFAULT.to_dict()
    del data["gamma"]
    with pytest.raises(TrainerError, match="missing trainer keys: gamma"):
        TrainerSpec.from_dict(data)
    with pytest.raises(TrainerError, match="no trainer file"):
        load_trainer_spec("nope")


# PPO math


def _rollout(rewards, values, dones, last_value):
    count = len(rewards)
    return Rollout(
        observations=torch.zeros(count, len(OBSERVATION_NAMES)),
        actions=torch.zeros(count, dtype=torch.long),
        log_probs=torch.zeros(count),
        values=torch.tensor(values, dtype=torch.float32),
        rewards=torch.tensor(rewards, dtype=torch.float32),
        dones=torch.tensor(dones, dtype=torch.float32),
        last_value=last_value,
    )


def test_advantages_by_hand():
    # gamma 0.5, lambda 1: each advantage is the discounted rest of the
    # episode, minus the value.
    rollout = _rollout([1, 1, 1], [0, 0, 0], [0, 0, 1], last_value=99)
    advantage, returns = advantages(rollout, gamma=0.5, gae_lambda=1.0)
    assert advantage.tolist() == [1.75, 1.5, 1.0]  # 99 is past the end
    assert returns.tolist() == [1.75, 1.5, 1.0]


def test_no_value_flows_across_an_episode_end():
    rollout = _rollout([1, 1], [2, 0], [1, 0], last_value=10)
    advantage, returns = advantages(rollout, gamma=0.5, gae_lambda=1.0)
    assert advantage.tolist() == [1 - 2, 1 + 0.5 * 10]
    assert returns.tolist() == [1, 6]


def test_lambda_zero_is_one_step():
    rollout = _rollout([1, 2], [3, 4], [0, 0], last_value=5)
    advantage, _ = advantages(rollout, gamma=0.5, gae_lambda=0.0)
    assert advantage.tolist() == [1 + 0.5 * 4 - 3, 2 + 0.5 * 5 - 4]


def test_an_update_favors_rewarded_actions(tmp_path):
    folder = create_agent("learner", load_model_spec("small"), root=tmp_path)
    network = load_agent(folder).network
    optimizer = torch.optim.Adam(network.parameters(), lr=0.003)
    generator = torch.Generator().manual_seed(0)
    observations = torch.zeros(256, len(OBSERVATION_NAMES))

    def probability_of_3():
        with torch.no_grad():
            logits, _ = network(observations[:1])
        return float(torch.softmax(logits[0], -1)[3])

    before = probability_of_3()
    for _ in range(5):
        with torch.no_grad():
            logits, values = network(observations)
        log_probs = torch.log_softmax(logits, -1)
        actions = torch.multinomial(log_probs.exp(), 1, generator=generator)
        actions = actions.squeeze(1)
        rollout = Rollout(
            observations=observations,
            actions=actions,
            log_probs=log_probs.gather(1, actions.unsqueeze(1)).squeeze(1),
            values=values,
            rewards=(actions == 3).float(),
            dones=torch.ones(256),
            last_value=0.0,
        )
        stats = update(network, optimizer, rollout, TINY, generator)
    assert probability_of_3() > before + 0.2
    assert stats.entropy > 0 and 0 <= stats.clip_fraction <= 1


# Training runs


def test_checkpoint_names():
    assert checkpoint_name(100_000) == "d0100k"
    assert checkpoint_name(1_000_000) == "d1000k"
    assert checkpoint_name(512) == "d0000512"


def test_a_training_run(tmp_path):
    summary = _train(tmp_path)
    folder = summary.folder
    assert folder.name.endswith("_train-pupil_seed0")
    for name in ("config.json", "metrics.csv", "learning.csv", "notes.md"):
        assert (folder / name).exists()

    learning = _rows(folder / "learning.csv")
    assert tuple(learning[0]) == LEARNING_COLUMNS
    assert [int(row["decisions"]) for row in learning] == [128, 256, 384, 512]
    metrics = _rows(folder / "metrics.csv")
    assert len(metrics) == summary.episodes >= 4  # 90 decisions a round
    assert [int(row["seed"]) for row in metrics[:3]] == [0, 1, 2]

    assert summary.checkpoints == ("d0000256", "d0000512")
    assert (summary.decisions, summary.updates) == (512, 4)
    config = json.loads((folder / "config.json").read_text())
    assert config["kind"] == "training"
    assert config["trainer"] == TINY.to_dict()
    assert config["agent"]["start_checkpoint"] == "initial"
    assert config["rules"] == SHORT.to_dict()


def test_the_newest_weights_drive(tmp_path):
    _train(tmp_path)
    agent = load_agent("pupil", root=tmp_path / "agents")
    assert (agent.checkpoint, agent.decisions) == ("d0000512", 512)
    driver = AgentDriver(agent)
    assert driver.record()["checkpoint"] == "d0000512"


def test_training_replays_verify(tmp_path):
    summary = _train(tmp_path)
    replays = sorted((summary.folder / "replays").glob("*.jsonl.gz"))
    assert replays
    for path in replays:
        replay = read_replay(path)
        assert replay.slots["1"]["training"]["run"] == summary.folder.name
        assert Replayer(replay).run().ok, path.name


def test_training_is_reproducible(tmp_path):
    first = _train(tmp_path / "a")
    second = _train(tmp_path / "b")

    def without_time(folder):
        rows = _rows(folder / "learning.csv")
        return [{**row, "seconds": None} for row in rows]

    assert without_time(first.folder) == without_time(second.folder)
    weights = [
        load_agent("pupil", root=tmp_path / name / "agents").network
        for name in "ab"
    ]
    for a, b in zip(weights[0].parameters(), weights[1].parameters()):
        assert torch.equal(a, b)


def test_a_second_phase_continues_the_agent(tmp_path):
    _train(tmp_path)
    summary = _train(tmp_path, first_seed=100)
    assert summary.checkpoints == ("d0000768", "d0001024")
    assert summary.agent_decisions == 1024
    config = json.loads((summary.folder / "config.json").read_text())
    assert config["agent"]["start_checkpoint"] == "d0000512"
    assert config["agent"]["start_decisions"] == 512


def test_ctrl_c_keeps_the_learned_weights(tmp_path):
    def stop_after_three(report):
        if report.update == 3:
            raise KeyboardInterrupt

    summary = _train(tmp_path, on_update=stop_after_three)
    assert summary.interrupted
    assert summary.checkpoints == ("d0000256", "d0000384")
    assert load_agent("pupil", root=tmp_path / "agents").decisions == 384
    saved = json.loads((summary.folder / "summary.json").read_text())
    assert saved["interrupted"] is True
    assert len(_rows(summary.folder / "learning.csv")) == 3


def test_training_runs_are_listed(tmp_path):
    _train(tmp_path)
    rows = list_runs(tmp_path / "runs")
    assert rows[0]["driver"] == "pupil" and rows[0]["status"] == "done"
    assert "pupil" in format_runs(rows)


def test_reward_scale_changes_learning_not_metrics(tmp_path):
    unscaled = TrainerSpec.from_dict({**TINY.to_dict(), "reward_scale": 1.0})
    scaled = TrainerSpec.from_dict({**TINY.to_dict(), "reward_scale": 0.01})
    plain = _train(tmp_path / "plain", trainer=unscaled)
    small = _train(tmp_path / "small", trainer=scaled)
    first = [_rows(s.folder / "metrics.csv")[0] for s in (plain, small)]
    assert first[0] == first[1]  # same game, same reward shown
    losses = [
        float(_rows(s.folder / "learning.csv")[0]["value_loss"])
        for s in (plain, small)
    ]
    assert losses[1] < losses[0] / 100  # the value head's error shrinks


def test_reward_scale_must_be_positive():
    with pytest.raises(TrainerError, match="reward_scale"):
        TrainerSpec.from_dict({**DEFAULT.to_dict(), "reward_scale": 0})
