"""Decision 032: the agent reward by term, and the reward bar under the
field. The reward values themselves must not change.
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
from src.render.layout import MARGIN, REWARD_HEIGHT, Layout  # noqa: E402
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


def test_the_bar_fits_by_dropping_detail():
    pygame.init()
    terms = {f"t{i}": -float(i + 1) * 1000 for i in range(12)}
    terms["points"] = 99999.0
    status = _status(terms)
    gains, costs = reward_groups(status)
    groups = [("GAINS", gains, None), ("COSTS", costs, None)]
    wide = panels._fit_groups(groups, 5000)
    assert "t0" in wide[1][2] and "other" not in wide[1][2]  # all of it
    medium = panels._fit_groups(groups, 800)
    assert "other" in medium[1][2]  # the first costs, the rest summed
    narrow = panels._fit_groups(groups, 400)
    assert narrow[1][2] == ""  # the totals only
    surface = pygame.Surface((900, 60))
    panels.draw_reward_bar(surface, pygame.Rect(0, 8, 855, 44), status)


def test_the_layout_stacks_the_bars():
    live = Layout.for_field(855, 480, reward=True)
    replay = Layout.for_field(855, 480, playback=True, reward=True)
    assert live.reward_bar.top == live.field_view.bottom + MARGIN
    assert replay.playback_bar.top == replay.field_view.bottom + MARGIN
    assert replay.reward_bar.top == replay.playback_bar.bottom + MARGIN
    plain = Layout.for_field(855, 480)
    assert live.window.h == plain.window.h + MARGIN + REWARD_HEIGHT
    assert live.left_panel.bottom == live.reward_bar.bottom
