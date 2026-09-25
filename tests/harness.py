"""Runs behavior scenarios against the pre-ECS (legacy) and ECS code.

The scenarios and fixtures are implementation-neutral: both runners must
produce identical snapshots. The legacy runner goes away in step 2d.
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


def _legacy_snapshot(env) -> dict:
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


Action = tuple[bool, bool, bool, bool]


def run_legacy(actions: list[Action]) -> list[dict]:
    """Returns the car snapshot after reset, then after every step."""
    from src.envs.maze_car.env import MazeCarEnv
    from src.envs.maze_car.models.action_state import ActionState

    setup_flags()
    _reset_singletons()
    env = MazeCarEnv()

    # Same path as MazeCarDemo.run, minus drawing and clock ticks,
    # which don't affect the physics.
    snapshots = [_legacy_snapshot(env)]
    for action in actions:
        env.action_state = ActionState(*action)
        env.update()
        snapshots.append(_legacy_snapshot(env))
    return snapshots


def _ecs_snapshot(world, car: int) -> dict:
    from src.sim.components import Hitbox, Motion, Sensors, Transform

    rect = world.component(car, Hitbox).rect
    transform = world.component(car, Transform)
    motion = world.component(car, Motion)
    return {
        "rect": [rect.x, rect.y, rect.width, rect.height],
        "angle": transform.angle,
        "speed": motion.speed,
        "acceleration": motion.acceleration_rate,
        "x_float": transform.x_float,
        "y_float": transform.y_float,
        "rays": {
            ray.name: {
                "start": [ray.start.x, ray.start.y],
                "end": [ray.end.x, ray.end.y],
                "distance": ray.distance,
            }
            for ray in world.component(car, Sensors).rays
        },
    }


def run_ecs(actions: list[Action]) -> list[dict]:
    """Same as run_legacy, through the ECS. Needs no global FLAGS."""
    from src.sim.components import ActionInput
    from src.sim.factories import create_start_car, create_world

    world = create_world(get_maze_car_config())
    car = create_start_car(world)

    snapshots = [_ecs_snapshot(world, car)]
    for action in actions:
        world.add_component(car, ActionInput(*action))
        world.step()
        snapshots.append(_ecs_snapshot(world, car))
    return snapshots


RUNNERS = {"legacy": run_legacy, "ecs": run_ecs}
