"""Decision 032: the agent reward by term (gains, costs, net) in the
AGENT card. The reward values themselves must not change.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from src.config import get_maze_car_config  # noqa: E402
from src.drivers.random_driver import RandomDriver  # noqa: E402
from src.envs.maze_car.env import MazeCarEnv  # noqa: E402
from src.envs.maze_car.rewards import StepEvents, load_reward_profile  # noqa
from src.render import panels  # noqa: E402
from src.render.layout import Layout  # noqa: E402
from src.render.panels import RewardStatus, reward_groups, signed  # noqa

EVENTS = StepEvents(
    points=3.0,
    checkpoints=1,
    damage=0.25,
    wrecked=False,
    contacts=1,
    stopped=True,
    time_up=False,
    distance=12.0,
    speed=-0.5,
    steering_change=0.3,
    closest_wall=0.1,
    checkpoint_seconds=(4.0,),
    distance_points=1.0,
)


@pytest.mark.parametrize("name", ["default", "time_bonus"])
def test_the_terms_sum_to_the_reward_exactly(name):
    profile = load_reward_profile(name)
    parts = profile.contributions(EVENTS)
    assert list(parts) == list(profile.terms)
    assert sum(parts.values()) == profile(EVENTS)  # bit for bit


def test_the_env_sums_each_term_over_the_game():
    config = get_maze_car_config()
    config.show_gui = False
    env = MazeCarEnv(config)  # headless, no recorder
    driver = RandomDriver(seed=3)
    observation, _ = env.reset(seed=5)
    for _ in range(600):
        observation, *_ = env.step(driver.act(observation))
    status = env.reward_status()
    assert set(status.terms) == set(status.weights)
    assert sum(status.terms.values()) == pytest.approx(status.total)
    assert status.terms["stopped"] <= 0  # a cost, if anything
    env.reset(seed=6)
    assert all(v == 0 for v in env.reward_status().terms.values())


def _status(terms, weights=None):
    if weights is None:
        weights = {t: 1.0 if v >= 0 else -1.0 for t, v in terms.items()}
    return RewardStatus("p", 0.0, sum(terms.values()), terms, weights)


def test_gains_and_costs():
    terms = {"points": 3901, "contact": -1200, "damage": -250, "stopped": -30}
    gains, costs = reward_groups(_status(terms))
    assert gains == [("points", 3901)]
    assert costs == [("contact", -1200), ("damage", -250), ("stopped", -30)]


def test_a_term_at_zero_goes_by_its_weight():
    status = _status(
        {"points": 0.0, "contact": 0.0}, {"points": 1.0, "contact": -100.0}
    )
    gains, costs = reward_groups(status)
    assert gains == [("points", 0.0)] and costs == [("contact", 0.0)]


def test_a_term_that_changed_sign_moves_group():
    status = _status({"speed": -12.0}, {"speed": 0.5})  # reversing
    assert reward_groups(status) == ([], [("speed", -12.0)])


def test_numbers():
    assert signed(3901.04) == "+3,901.0"
    assert signed(-1480) == "-1,480.0"
    assert signed(0.0) == "0.0" and signed(-0.01) == "0.0"


def test_the_agent_card_shows_gains_costs_and_the_biggest_cost():
    """No bottom bar: all of it in the AGENT card (5 rows fit)."""
    pygame.init()
    config = get_maze_car_config()
    config.show_gui = False
    env = MazeCarEnv(config)
    surface = pygame.Surface((300, 700))
    drawn = []
    real = panels.draw_text

    def spy(surface, text, *args, **kwargs):
        drawn.append(text)
        return real(surface, text, *args, **kwargs)

    status = _status(
        {"points": 3901.0, "contact": -1200.0, "damage": -250.0}
    )
    panels.draw_text = spy
    try:
        panels.draw_game_panel(
            surface, pygame.Rect(16, 16, 250, 640), env.world, [], status
        )
    finally:
        panels.draw_text = real
    assert "AGENT · p" in drawn
    for text in ("Gains", "+3,901.0", "Costs", "-1,450.0", "Net"):
        assert text in drawn
    assert "contact -1,200.0" in drawn  # the biggest cost
    assert any(t.startswith("step ") and t.endswith("/s") for t in drawn)


def test_no_bottom_bar():
    layout = Layout.for_field(855, 480)
    assert not hasattr(layout, "reward_bar")
