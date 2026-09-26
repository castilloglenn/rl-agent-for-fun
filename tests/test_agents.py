"""Agent core: models, network, stored agents, agent driver (5a1)."""

import json

import numpy as np
import pytest
import torch

from src.agents.driver import AgentDriver
from src.agents.model import (
    MODELS_DIR,
    ModelError,
    ModelSpec,
    load_model_spec,
)
from src.agents.store import AgentError, create_agent, load_agent
from src.config import get_maze_car_config
from src.drivers.actions import CANONICAL_ACTIONS
from src.drivers.episode import run_episode
from src.drivers.registry import make_driver
from src.envs.maze_car.env import MazeCarEnv
from src.experiments.runner import run_experiment
from src.sim.observation import OBSERVATION_NAMES
from src.sim.rules import load_rules

SMALL = load_model_spec("small")


def _observations(count=20, seed=0):
    rng = np.random.default_rng(seed)
    return rng.uniform(-1, 1, (count, len(OBSERVATION_NAMES))).astype(
        np.float32
    )


def _env():
    config = get_maze_car_config()
    config.show_gui = False
    return MazeCarEnv(config)


# Models


def test_model_files_load_and_round_trip():
    for path in MODELS_DIR.glob("*.json"):
        spec = load_model_spec(str(path))
        assert spec.to_dict() == json.loads(path.read_text()), path.name


@pytest.mark.parametrize(
    "change, message",
    [
        ({"format": 2}, "unsupported model format"),
        ({"hidden": []}, "positive layer sizes"),
        ({"hidden": [64, 0]}, "positive layer sizes"),
        ({"activation": "sigmoid"}, "unknown activation"),
        ({"actions": "all32"}, "unknown action set"),
        ({"action_repeat": 0}, "action_repeat"),
    ],
)
def test_invalid_models_are_rejected(change, message):
    with pytest.raises(ModelError, match=message):
        ModelSpec.from_dict({**SMALL.to_dict(), **change})


# Stored agents


def test_create_agent(tmp_path):
    folder = create_agent("rookie", SMALL, seed=3, root=tmp_path)
    assert json.loads((folder / "model.json").read_text()) == SMALL.to_dict()
    assert (folder / "checkpoints" / "initial.pt").exists()
    agent = load_agent("rookie", root=tmp_path)
    assert agent.checkpoint == "initial"
    logits, values = agent.network(torch.as_tensor(_observations()))
    assert logits.shape == (20, 12) and values.shape == (20,)


def test_same_seed_same_weights(tmp_path):
    create_agent("a", SMALL, seed=1, root=tmp_path)
    create_agent("b", SMALL, seed=1, root=tmp_path)
    create_agent("c", SMALL, seed=2, root=tmp_path)
    x = torch.as_tensor(_observations())
    out = {
        name: load_agent(name, root=tmp_path).network(x)[0]
        for name in "abc"
    }
    assert torch.equal(out["a"], out["b"])
    assert not torch.equal(out["a"], out["c"])


def test_creating_does_not_change_global_randomness(tmp_path):
    torch.manual_seed(123)
    expected = torch.rand(3)
    torch.manual_seed(123)
    create_agent("a", SMALL, seed=9, root=tmp_path)
    assert torch.equal(torch.rand(3), expected)


def test_bad_ids_and_duplicates(tmp_path):
    with pytest.raises(AgentError, match="letters, digits"):
        create_agent("my agent!", SMALL, root=tmp_path)
    create_agent("dup", SMALL, root=tmp_path)
    with pytest.raises(AgentError, match="already exists"):
        create_agent("dup", SMALL, root=tmp_path)


def test_a_checkpoint_only_loads_into_its_own_model(tmp_path):
    """Safety rule from decision 014."""
    folder = create_agent("strict", SMALL, root=tmp_path)
    medium = load_model_spec("medium").to_dict()
    (folder / "model.json").write_text(json.dumps(medium))
    with pytest.raises(AgentError, match="another model"):
        load_agent("strict", root=tmp_path)


def test_observation_version_mismatch_is_refused(tmp_path):
    old = ModelSpec.from_dict({**SMALL.to_dict(), "observation_version": 99})
    with pytest.raises(AgentError, match="observation version"):
        create_agent("future", old, root=tmp_path)


def test_newest_or_named_checkpoint(tmp_path):
    from src.agents.store import save_checkpoint

    folder = create_agent("multi", SMALL, seed=1, root=tmp_path)
    agent = load_agent("multi", root=tmp_path)
    with torch.no_grad():
        for parameter in agent.network.parameters():
            parameter.add_(1.0)
    save_checkpoint(folder, "later", agent.network, SMALL)
    assert load_agent("multi", root=tmp_path).checkpoint == "later"
    first = load_agent("multi", checkpoint="initial", root=tmp_path)
    assert first.checkpoint == "initial"


# The driver


def _driver(tmp_path, deterministic=True, seed=0):
    create_agent("driver", SMALL, seed=seed, root=tmp_path)
    return AgentDriver(
        load_agent("driver", root=tmp_path), deterministic=deterministic
    )


def test_agent_decides_every_4_steps(tmp_path):
    driver = _driver(tmp_path)
    observations = _observations(40)
    actions = [driver.act(observations[i]) for i in range(40)]
    assert all(action in CANONICAL_ACTIONS for action in actions)
    assert all(actions[i] == actions[i - i % 4] for i in range(40))


def test_deterministic_and_seeded_sampling(tmp_path):
    driver = _driver(tmp_path, deterministic=False)
    observations = _observations(80)
    driver.reset(5)
    first = [driver.act(o) for o in observations]
    driver.reset(5)
    assert [driver.act(o) for o in observations] == first
    driver.reset(6)
    assert [driver.act(o) for o in observations] != first


def test_record_and_label(tmp_path):
    driver = _driver(tmp_path)
    assert driver.record() == {
        "type": "agent",
        "id": "driver",
        "checkpoint": "initial",
    }
    assert driver.label == "driver (agent)"


def test_agents_play_through_the_env_and_the_runner(tmp_path):
    driver = _driver(tmp_path)
    result = run_episode(_env(), driver, seed=1)
    assert result.steps > 0
    summary = run_experiment(
        "agent",
        driver,
        get_maze_car_config(),
        episodes=2,
        rules=load_rules("standard").with_round_seconds(3),
        runs_dir=tmp_path / "runs",
    )
    config = json.loads((summary.folder / "config.json").read_text())
    assert config["driver"]["type"] == "agent"


def test_registry_loads_agents_by_path_and_checkpoint(tmp_path):
    folder = create_agent("reg", SMALL, root=tmp_path)
    driver = make_driver(f"agent:{folder}")
    assert isinstance(driver, AgentDriver)
    assert make_driver(f"agent:{folder}@initial").record()["checkpoint"] == (
        "initial"
    )


def test_missing_agents_are_a_driver_error(tmp_path):
    from src.drivers.registry import DriverError

    with pytest.raises(DriverError, match="no agent at"):
        make_driver(f"agent:{tmp_path / 'missing'}")
