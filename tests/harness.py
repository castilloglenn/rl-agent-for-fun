"""Runs behavior scenarios against the current (pre-ECS) implementation.

The scenarios and fixtures are implementation-neutral. After the ECS
refactor, only `run_scenario` should need rewriting; the fixtures must
still match.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from absl import flags  # noqa: E402
from ml_collections import config_flags  # noqa: E402

import src.config  # noqa: E402,F401  (defines the tests/demo flags)
from src.config import get_agent_config, get_maze_car_config  # noqa: E402

FLAGS = flags.FLAGS


def setup_flags() -> None:
    if "maze_car" not in FLAGS:
        config_flags.DEFINE_config_dict("agent", get_agent_config())
        config_flags.DEFINE_config_dict("maze_car", get_maze_car_config())
    if not FLAGS.is_parsed():
        FLAGS(["tests"])


def config_snapshot() -> dict:
    config = FLAGS.maze_car
    return {
        "window": [config.window.width, config.window.height],
        "fps": config.display.fps,
        "car": [config.car.width, config.car.height],
        "acceleration_unit": config.car.acceleration_unit,
        "acceleration_max": config.car.acceleration_max,
    }


def _reset_singletons() -> None:
    from src.envs.maze_car.sprites.field import FieldSingleton
    from src.envs.maze_car.state import StateSingleton

    StateSingleton._instance = None
    FieldSingleton._instance = None


def _snapshot(env) -> dict:
    car = env.car.state
    rays = {
        "front": env.car.front_collision.state,
        "left": env.car.left_collision.state,
        "right": env.car.right_collision.state,
        "back": env.car.back_collision.state,
    }
    return {
        "rect": [car.rect.x, car.rect.y, car.rect.width, car.rect.height],
        "angle": car.angle,
        "speed": car.speed_multiplier,
        "acceleration": car.acceleration_rate,
        "x_float": car.x_float,
        "y_float": car.y_float,
        "rays": {
            name: {
                "start": [ray.start.x, ray.start.y],
                "end": [ray.end.x, ray.end.y],
                "distance": ray.distance,
            }
            for name, ray in rays.items()
        },
    }


def run_scenario(actions: list[tuple[bool, bool, bool, bool]]) -> list[dict]:
    """Returns the car snapshot after reset, then after every step."""
    from src.envs.maze_car.env import MazeCarEnv
    from src.envs.maze_car.models.action_state import ActionState

    setup_flags()
    _reset_singletons()
    env = MazeCarEnv()

    # Same path as MazeCarDemo.run, minus drawing and clock ticks,
    # which don't affect the physics.
    snapshots = [_snapshot(env)]
    for action in actions:
        env.action_state = ActionState(*action)
        env.update()
        snapshots.append(_snapshot(env))
    return snapshots
