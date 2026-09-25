"""Runs behavior scenarios through the ECS simulation.

The scenarios and fixtures are implementation-neutral. The fixtures were
recorded from the pre-ECS code, and the ECS matched them exactly before
that code was removed.
"""

from src.config import get_maze_car_config
from src.ecs import World
from src.sim.components import ActionInput, Hitbox, Motion, Sensors, Transform

Action = tuple[bool, bool, bool, bool]


def config_snapshot() -> dict:
    config = get_maze_car_config()
    return {
        "field": [
            config.field.x,
            config.field.y,
            config.field.width,
            config.field.height,
        ],
        "ray_length": config.sensors.ray_length,
        "fps": config.display.fps,
        "car": [config.car.width, config.car.height],
        "acceleration_unit": config.car.acceleration_unit,
        "acceleration_max": config.car.acceleration_max,
    }


def _snapshot(world: World, car: int) -> dict:
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


def run_world(actions: list[Action]) -> list[dict]:
    """Returns the car snapshot after creation, then after every step."""
    from src.sim.factories import create_start_car, create_world

    world = create_world(get_maze_car_config())
    car = create_start_car(world)

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
