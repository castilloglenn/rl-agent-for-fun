"""Runs behavior scenarios through the ECS simulation.

The scenarios and fixtures are implementation-neutral. The fixtures were
recorded from the pre-ECS code, and the ECS matched them exactly before
that code was removed.
"""

from src.config import game_config, get_maze_car_config
from src.ecs import World
from src.sim.components import (
    ActionInput,
    Eliminated,
    Motion,
    Score,
    Sensors,
    Transform,
)

Action = tuple[bool, bool, bool, bool, bool]


def config_snapshot() -> dict:
    """The game-defining config: fixtures fail if any of it changes."""
    return game_config(get_maze_car_config())


def _snapshot(world: World, car: int) -> dict:
    transform = world.component(car, Transform)
    motion = world.component(car, Motion)
    eliminated = world.try_component(car, Eliminated)
    return {
        "center": [transform.x, transform.y],
        "angle": transform.angle,
        "speed": motion.speed,
        "pedal": motion.pedal,
        "steering": motion.steering,
        "eliminated": eliminated.reason if eliminated else None,
        "score": world.component(car, Score).total,
        # Start and end points follow from the pose and distance
        # (tests/test_sensors.py checks them), so only distances are kept.
        "rays": {
            ray.name: ray.distance
            for ray in world.component(car, Sensors).rays
        },
    }


def run_world(actions: list[Action]) -> list[dict]:
    """Returns the car snapshot after creation, then after every step."""
    from src.sim.factories import create_game

    world, car = create_game(get_maze_car_config())

    snapshots = [_snapshot(world, car)]
    for action in actions:
        world.add_component(car, ActionInput(*action))
        world.step()
        snapshots.append(_snapshot(world, car))
    return snapshots


def run_env(actions: list[Action]) -> list[dict]:
    """Same as run_world, through MazeCarEnv.game_step, headless."""
    from src.envs.maze_car.env import MazeCarEnv

    config = get_maze_car_config()
    config.show_gui = False
    env = MazeCarEnv(config)

    snapshots = [_snapshot(env.world, env.car)]
    for action in actions:
        env.game_step(action)
        snapshots.append(_snapshot(env.world, env.car))
    return snapshots


RUNNERS = {"world": run_world, "env": run_env}
