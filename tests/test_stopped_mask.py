"""Stopped, an agent must press gas or reverse (7f6): at speed 0 the
other pedals can't move the car, and steering needs speed.
"""

import torch

from src.agents.model import load_model_spec
from src.agents.network import PolicyNetwork, SPEED
from src.drivers.actions import CANONICAL_NAMES
from src.sim.observation import OBSERVATION_NAMES

MOVING = {
    i for i, n in enumerate(CANONICAL_NAMES)
    if n.split("+")[1] in ("gas", "reverse")
}


def _network():
    torch.manual_seed(0)
    return PolicyNetwork(
        load_model_spec("small"), len(OBSERVATION_NAMES), 12
    )


def test_a_stopped_car_can_only_press_gas_or_reverse():
    network = _network()
    stopped = torch.zeros(1, len(OBSERVATION_NAMES))
    moving = stopped.clone()
    moving[0, SPEED] = 0.4
    with torch.no_grad():
        p_stopped = torch.softmax(network(stopped)[0][0], -1)
        p_moving = torch.softmax(network(moving)[0][0], -1)
    for i in range(12):
        if i in MOVING:
            assert p_stopped[i] > 0
        else:
            assert p_stopped[i] == 0, CANONICAL_NAMES[i]  # none, brake
    assert all(p > 0 for p in p_moving)  # moving: braking, coasting too
    assert len(MOVING) == 6
    assert abs(float(p_stopped.sum()) - 1) < 1e-6


def test_entropy_stays_finite_with_blocked_actions():
    network = _network()
    stopped = torch.zeros(8, len(OBSERVATION_NAMES))
    log_probs = torch.log_softmax(network(stopped)[0], -1)
    entropy = -(log_probs.exp() * log_probs).sum(-1)
    assert torch.isfinite(entropy).all() and (entropy > 0).all()


def test_the_driver_never_sits_still(tmp_path):
    """Greedy or sampled, a stopped agent's pick moves the car."""
    from src.agents.driver import AgentDriver
    from src.agents.store import create_agent, load_agent
    from src.drivers.actions import canonical_index

    folder = create_agent("still", load_model_spec("small"), root=tmp_path)
    stopped = torch.zeros(len(OBSERVATION_NAMES)).numpy()
    for deterministic in (True, False):
        driver = AgentDriver(load_agent(folder), deterministic=deterministic)
        for seed in range(20):
            driver.reset(seed)
            assert canonical_index(driver.act(stopped)) in MOVING
