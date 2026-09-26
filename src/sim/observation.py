"""What an agent sees: 14 normalized numbers.

The layout is versioned. A trained agent records the version it was
trained on, so an incompatible agent is caught when loaded. Change the
version whenever the layout or normalization changes. See
docs/game-design.md (Observation).
"""

import math

import numpy as np

from src.ecs import World
from src.sim.components import (
    Checkpoint,
    Health,
    Motion,
    Sensors,
    Transform,
)
from src.sim.resources import Field, RoundState, SimConfig
from src.sim.systems.sensors import RAY_LAYOUT

OBSERVATION_VERSION = 1

OBSERVATION_NAMES = (
    *(f"ray_{name}" for name, _ in RAY_LAYOUT),  # 0..1, of field diagonal
    "speed",  # -1/3 (full reverse) .. 1 (max speed)
    "steering",  # -1 (full right) .. 1 (full left)
    "checkpoint_distance",  # 0..1, of field diagonal
    "checkpoint_sin",  # relative angle: + is to the left
    "checkpoint_cos",  # relative angle: + is ahead
    "time_left",  # 1 at the start of the round .. 0
    "health",  # 1 (full) .. 0 (wrecked)
)


def observe(world: World, car: int) -> np.ndarray:
    """The car's observation, in OBSERVATION_NAMES order (float32)."""
    field = world.resource(Field).rect
    diagonal = math.hypot(field.width, field.height)
    transform = world.component(car, Transform)
    motion = world.component(car, Motion)
    sim = world.resource(SimConfig)
    state = world.resource(RoundState)

    sensors = world.component(car, Sensors)
    rays = {ray.name: ray.distance for ray in sensors.rays}
    values = [min(rays[name] / diagonal, 1.0) for name, _ in RAY_LAYOUT]
    values.append(motion.speed * sim.steps_per_second / sim.max_speed)
    values.append(motion.steering)
    values.extend(_checkpoint_compass(world, transform, diagonal))
    values.append(state.steps_left / state.steps_total)
    values.append(world.component(car, Health).share)
    return np.array(values, dtype=np.float32)


def _checkpoint_compass(
    world: World, transform: Transform, diagonal: float
) -> tuple[float, float, float]:
    """Distance, sin and cos of the nearest checkpoint, relative to the
    car's heading. With no checkpoint: (1, 0, 0).
    """
    spots = [spot for _, (spot, _) in world.query(Transform, Checkpoint)]
    if not spots:
        return 1.0, 0.0, 0.0
    here = (transform.x, transform.y)
    spot = min(spots, key=lambda s: math.dist((s.x, s.y), here))
    distance = math.dist((spot.x, spot.y), here)
    # Screen y grows downward, so flip it for a counterclockwise angle.
    bearing = math.atan2(-(spot.y - transform.y), spot.x - transform.x)
    relative = bearing - math.radians(transform.angle)
    return (
        min(distance / diagonal, 1.0),
        math.sin(relative),
        math.cos(relative),
    )
