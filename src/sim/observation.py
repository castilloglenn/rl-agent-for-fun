"""What an agent sees: 39 normalized numbers (9b, decision 077).

The layout is versioned. A trained agent records the version it was
trained on, so an incompatible agent is caught when loaded. The project
keeps version 1 and starts agents from scratch when the layout changes.
See docs/game-design.md (Observation).
"""

import math

import numpy as np

from src.ecs import World
from src.sim.components import Health, Motion, Sensors, Tank, Transform
from src.sim import route
from src.sim.resources import RoundState, SimConfig
from src.sim.systems.sensors import RAY_LAYOUT

OBSERVATION_VERSION = 1
# Rays and the fuel distance are divided by this on every map (7d2,
# decision 042): the box's diagonal, so a number means the same distance
# everywhere, and farther than this reads 1 ("far"). On a box-sized map
# it's what the field's diagonal gave before, to the bit.
DISTANCE_SCALE = math.hypot(855, 480)  # px, about 980.5

FUEL_SLOTS = 3  # the fuels sensed: up to 3 are out at once (9a2)
# Each fuel slot, nearest by route first. An empty slot (fewer out) reads
# present 0, far (1), and no direction (0, 0).
SLOT = (
    "present",  # 1: a fuel is in this slot, 0: none
    "distance",  # straight, 0..1 of DISTANCE_SCALE
    "sin",  # its relative angle: + is to the left
    "cos",  # + is ahead
    # The remembered route (7f7): its distance, and the direction of a
    # waypoint about one corner ahead along it, relative to the heading.
    "route_distance",  # 0..1, of DISTANCE_SCALE
    "route_sin",  # + is to the left
    "route_cos",  # + is ahead
)
EMPTY_SLOT = (0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

OBSERVATION_NAMES = (
    *(f"ray_{name}" for name, _ in RAY_LAYOUT),  # 0..1, of DISTANCE_SCALE
    "speed",  # -1/3 (full reverse) .. 1 (max speed)
    "steering",  # -1 (full right) .. 1 (full left)
    "tank",  # 1 (full) .. 0 (empty); 1 with no tank in the rules
    *(f"fuel{k}_{name}" for k in range(1, FUEL_SLOTS + 1) for name in SLOT),
    "stuck",  # 0..1: seconds since it last got closer, of STUCK_CAP
    "time_left",  # 1 at the start of the round .. 0
    "health",  # 1 (full) .. 0 (wrecked)
)


def fuel_slots(values: dict) -> list[dict]:
    """The fuel slots that hold a fuel, nearest by route first, each as
    {"distance", "sin", "cos", "route_distance", ...} from an observation
    read as {name: value} (the hand-written drivers).
    """
    found = []
    for k in range(1, FUEL_SLOTS + 1):
        if values[f"fuel{k}_present"] > 0.5:
            found.append({name: values[f"fuel{k}_{name}"] for name in SLOT})
    return found


NO_FUEL = dict(zip(SLOT, EMPTY_SLOT))  # what a driver aims at with none


def observe(world: World, car: int) -> np.ndarray:
    """The car's observation, in OBSERVATION_NAMES order (float32)."""
    scale = DISTANCE_SCALE
    transform = world.component(car, Transform)
    motion = world.component(car, Motion)
    sim = world.resource(SimConfig)
    state = world.resource(RoundState)

    sensors = world.component(car, Sensors)
    rays = {ray.name: ray.distance for ray in sensors.rays}
    values = [min(rays[name] / scale, 1.0) for name, _ in RAY_LAYOUT]
    values.append(motion.speed * sim.steps_per_second / sim.max_speed)
    values.append(motion.steering)
    tank = world.try_component(car, Tank)
    values.append(tank.share if tank else 1.0)
    sense = route.sense(world, car)
    for k in range(FUEL_SLOTS):
        held = sense.routes[k] if k < len(sense.routes) else None
        values.extend(_slot(held, transform, scale))
    stuck = route.stuck_seconds(world, sense) / route.STUCK_CAP
    values.append(min(stuck, 1.0))
    values.append(state.steps_left / state.steps_total)
    values.append(world.component(car, Health).share)
    return np.array(values, dtype=np.float32)


def _slot(held, transform: Transform, scale: float) -> tuple:
    """A fuel slot: present, its straight compass, and its remembered
    route (distance, and the waypoint's direction).
    """
    if held is None or held.waypoint is None:
        return EMPTY_SLOT
    distance, sin, cos = _bearing(held.goal, transform)
    _, route_sin, route_cos = _bearing(held.waypoint, transform)
    return (
        1.0,
        min(distance / scale, 1.0),
        sin,
        cos,
        min(held.distance / scale, 1.0),
        route_sin,
        route_cos,
    )


def _bearing(spot, transform: Transform) -> tuple[float, float, float]:
    """Distance to `spot`, and the sin and cos of its angle relative to
    the car's heading.
    """
    x, y = spot
    distance = math.dist((x, y), (transform.x, transform.y))
    # Screen y grows downward, so flip it for a counterclockwise angle.
    bearing = math.atan2(-(y - transform.y), x - transform.x)
    relative = bearing - math.radians(transform.angle)
    return distance, math.sin(relative), math.cos(relative)
