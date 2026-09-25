from ml_collections import ConfigDict

from src.ecs import World
from src.sim.components import (
    ActionInput,
    CarSpec,
    Checkpoint,
    Hitbox,
    Motion,
    PreviousPose,
    Ray,
    Renderable,
    Respawn,
    Score,
    ScoreReward,
    Sensors,
    Transform,
    Trigger,
)
from src.sim.geometry import body_edge_distance
from src.sim.resources import (
    EventLog,
    Field,
    GameRules,
    Rng,
    RoundState,
    SimClock,
    SimConfig,
)
from src.sim.systems import SIMULATION_SYSTEMS
from src.sim.systems.sensors import RAY_LAYOUT, cast_rays
from src.sim.systems.triggers import random_spot
from src.utils.types import Colors, ColorValue


def create_game(
    config: ConfigDict, label: str = "Car 1", seed: int | None = None
) -> tuple[World, int]:
    """The first-goal game: one car in the box map, plus a checkpoint.
    Returns the world and the car.
    """
    world = create_world(config, seed)
    car = create_start_car(world, label=label)
    create_checkpoint(world)
    return world, car


def create_world(config: ConfigDict, seed: int | None = None) -> World:
    """seed: for everything random (checkpoint spawns). Defaults to
    `game.seed`.
    """
    world = World()
    world.add_resource(SimConfig.from_config(config))
    world.add_resource(GameRules.from_config(config))
    world.add_resource(Rng(config.game.seed if seed is None else seed))
    world.add_resource(Field.from_config(config))
    world.add_resource(SimClock())
    world.add_resource(
        RoundState(
            steps_left=config.round.seconds * config.sim.steps_per_second,
            total=config.game.rounds,
        )
    )
    world.add_resource(EventLog())
    for system in SIMULATION_SYSTEMS:
        world.add_system(system)
    return world


def create_car(
    world: World,
    x: float,
    y: float,
    width: int,
    height: int,
    color: ColorValue,
    label: str = "Car",
    angle: float = 0.0,
) -> int:
    """A car centered at (x, y) in world coordinates."""
    config = world.resource(SimConfig)
    transform = Transform(x=x, y=y, angle=angle)
    sensors = Sensors(
        rays=[
            Ray(
                name,
                angle=ray_angle,
                offset=body_edge_distance(ray_angle, width, height),
            )
            for name, ray_angle in RAY_LAYOUT
        ]
    )
    cast_rays(sensors, transform, world.resource(Field), config.ray_length)

    return world.create_entity(
        ActionInput(),
        transform,
        Motion(),
        _car_spec(config),
        Hitbox(width=width, height=height),
        sensors,
        PreviousPose(x, y, angle),
        Score(),
        Renderable(color=color, label=label),
    )


def create_start_car(
    world: World,
    color: ColorValue = Colors.SKY_BLUE,
    label: str = "Car 1",
) -> int:
    """A car at the starting position: left quarter, mid height, facing
    right.
    """
    field = world.resource(Field)
    config = world.resource(SimConfig)
    return create_car(
        world,
        x=field.x + field.width / 4,
        y=field.y + field.height / 2,
        width=config.car_width,
        height=config.car_height,
        color=color,
        label=label,
    )


def create_checkpoint(world: World) -> int:
    """A checkpoint at a seeded random spot, away from every car."""
    rules = world.resource(GameRules)
    cars = world.query(Transform, Hitbox)
    avoid = (cars[0][1][0].x, cars[0][1][0].y) if cars else (-1e9, -1e9)
    x, y = random_spot(world, avoid=avoid)
    return world.create_entity(
        Transform(x=x, y=y),
        Trigger(radius=rules.checkpoint_radius),
        ScoreReward(points=rules.checkpoint_points, label="checkpoint"),
        Respawn(),
        Checkpoint(),
    )


def _car_spec(config: SimConfig) -> CarSpec:
    """Converts px/s and px/s² to per-step units."""
    fps = config.steps_per_second
    return CarSpec(
        max_speed=config.max_speed / fps,
        max_reverse_speed=config.max_reverse_speed / fps,
        acceleration=config.acceleration / fps**2,
        reverse_acceleration=config.reverse_acceleration / fps**2,
        brake_deceleration=config.brake_deceleration / fps**2,
        drag=config.drag / fps**2,
        max_turn_rate=config.max_turn_rate / fps,
        full_turn_speed=config.full_turn_speed / fps,
        steer_rate=1 / (config.steer_in_time * fps),
        steer_return_rate=1 / (config.steer_return_time * fps),
    )
