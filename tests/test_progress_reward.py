"""The progress reward (roadmap 7e, decision 041): px closer to the
fuel along a drivable path, gains while reversing at a share,
losses in full.
"""

from src.config import get_maze_car_config
from src.drivers.registry import make_driver
from src.envs.maze_car.env import MazeCarEnv
from src.envs.maze_car.rewards import TERMS, RewardProfile, StepEvents
from src.sim.rules import load_rules


def _events(progress, reversing=False):
    return StepEvents(
        points=0, fuels=0, damage=0.0, wrecked=False, contacts=0,
        stopped=False, time_up=False, distance=0.0, speed=0.0,
        steering_change=0.0, closest_wall=1.0,
        progress=progress, reversing=reversing,
    )


def test_reversing_gains_count_half_and_losses_in_full():
    term = TERMS["progress"]
    assert term(_events(2.0)) == 2.0
    assert term(_events(2.0, reversing=True)) == 1.0
    assert term(_events(-2.0, reversing=True)) == -2.0
    assert term(_events(2.0, True), {"reverse": 0.1}) == 0.2


def test_rocking_back_and_forth_never_gains():
    term = TERMS["progress"]
    for there, back in ((True, False), (False, True)):
        # Away one way, closer the other: 10 px each.
        loop = term(_events(-10.0, there)) + term(_events(10.0, back))
        assert loop <= 0


def _run(stage, steps=900):
    config = get_maze_car_config()
    config.show_gui = False
    config.stage = stage
    profile = RewardProfile.from_dict(
        {"format": 1, "name": "test", "terms": {"progress": 1.0}}
    )
    env = MazeCarEnv(config, rules=load_rules("standard"), reward=profile)
    env.reset(seed=4)
    driver = make_driver("heuristic")
    driver.reset(4)
    rewards, fuels = [], 0
    for _ in range(steps):
        _, reward, done, cut, info = env.step(driver.act(env.last_observation))
        rewards.append(reward)
        fuels = info["fuels"]
        if done or cut:
            break
    return rewards, fuels


def test_driving_to_fuels_pays_without_jumps():
    rewards, fuels = _run("box")
    assert fuels >= 2  # it reached some, and the next one spawned
    assert sum(rewards) > 200
    # On the box the path is the straight line: a step is at most the px
    # driven (300 px/s at 120 steps/s: 2.5 px), never a jump at a spawn.
    assert max(abs(r) for r in rewards) <= 2.6


def test_around_walls_it_pays_too_and_stays_small_per_step():
    rewards, fuels = _run("pillars")
    assert fuels >= 1 and sum(rewards) > 100
    # The grid's path runs up to 8 % longer than a straight line, and next
    # to a wall a step can gain a little more than the px driven (under 2
    # steps' worth), never a jump. It's still "before minus after" at the
    # same spots, so driving back past it gives it back: nothing to farm.
    assert max(abs(r) for r in rewards) <= 2 * 2.5
