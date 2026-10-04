"""The navigator (7f12): a teacher that follows the route. Not scored:
the heuristic stays the 1.0 bar.
"""

from src.config import get_maze_car_config
from src.drivers.episode import run_episode
from src.drivers.heuristic import CompassDriver
from src.drivers.navigator import Navigator
from src.drivers.registry import make_driver
from src.envs.maze_car.env import MazeCarEnv
from src.sim.stage import load_stage


def _rate(driver_class, stage, seeds=range(80_000, 80_003)):
    config = get_maze_car_config()
    config.show_gui = False
    env = MazeCarEnv(config, stage=load_stage(stage))
    results = [run_episode(env, driver_class(), seed) for seed in seeds]
    return sum(r.fuels for r in results)


def test_it_goes_around_walls_where_the_heuristic_cant():
    """course_small: every leg crosses walls. The heuristic aims through
    them; the navigator follows the route.
    """
    assert _rate(Navigator, "course_small") >= 5 * max(
        _rate(CompassDriver, "course_small"), 1
    )


def test_it_does_at_least_as_well_on_open_maps():
    assert _rate(Navigator, "box") >= _rate(CompassDriver, "box")


def test_it_backs_out_when_stuck():
    from src.sim.observation import OBSERVATION_NAMES

    observation = [0.5] * len(OBSERVATION_NAMES)
    for name in ("ray_front", "ray_front_left_15", "ray_front_right_15"):
        observation[OBSERVATION_NAMES.index(name)] = 0.01  # a wall
    observation[OBSERVATION_NAMES.index("stuck")] = 0.5  # for 5 s
    observation[OBSERVATION_NAMES.index("route_sin")] = 0.8  # to the left
    driver = Navigator()
    action = driver.act(observation)
    assert action[3] and action[1]  # reverse, wheel right: front swings left


def test_it_is_a_driver_to_record_and_watch():
    assert make_driver("navigator").record() == {
        "type": "baseline", "id": "navigator",
    }
    from src.experiments.driver_rounds import player_of

    assert player_of("navigator") == "Navigator"
