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
    SpawnedAt,
    Transform,
    Trigger,
)
from src.sim.geometry import body_edge_distance
from src.sim.resources import (
    EventLog,
    Field,
    Rng,
    RoundState,
    SimClock,
    SimConfig,
    SpawnSchedules,
)
from src.sim.rules import Rules, load_rules
from src.sim.spawning import SpawnSchedule
from src.sim.stage import Stage, load_stage
from src.sim.systems import SIMULATION_SYSTEMS
from src.sim.systems.sensors import RAY_LAYOUT, cast_rays
from src.sim.systems.triggers import next_spawn
from src.utils.types import Colors, ColorValue


def create_game(
    config: ConfigDict,
    label: str = "Car 1",
    seed: int | None = None,
    stage: Stage | None = None,
    rules: Rules | None = None,
) -> tuple[World, int]:
    """The first-goal game: one car at the stage's spawn, plus a
    checkpoint. Returns the world and the car.
    """
    world = create_world(config, seed, stage, rules)
    car = create_start_car(world, label=label)
    create_checkpoint(world)
    return world, car


def create_world(
    config: ConfigDict,
    seed: int | None = None,
    stage: Stage | None = None,
    rules: Rules | None = None,
) -> World:
    """seed: for everything random (spawn schedules). Defaults to
    `game.seed`. stage and rules: default to loading `config.stage` and
    `config.rules` (a replay passes its embedded ones instead).
    """
    stage = stage or load_stage(config.stage)
    rules = rules or load_rules(config.rules)
    seed = config.game.seed if seed is None else seed
    world = World()
    world.add_resource(SimConfig.from_config(config))
    world.add_resource(rules)
    world.add_resource(Rng(seed))
    world.add_resource(stage)
    world.add_resource(Field.from_stage(stage))
    world.add_resource(
        SpawnSchedules(
            {
                "checkpoints": SpawnSchedule(
                    "checkpoints",
                    seed,
                    stage.checkpoints,
                    stage.width,
                    stage.height,
                )
            }
        )
    )
    world.add_resource(SimClock())
    round_steps = round(rules.round_seconds * config.sim.steps_per_second)
    world.add_resource(
        RoundState(
            steps_left=round_steps,
            steps_total=round_steps,
            total=rules.rounds,
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
    """A car at the stage's first spawn."""
    spawn = world.resource(Stage).spawns[0]
    config = world.resource(SimConfig)
    return create_car(
        world,
        x=spawn.x,
        y=spawn.y,
        width=config.car_width,
        height=config.car_height,
        color=color,
        label=label,
        angle=spawn.angle,
    )


def create_checkpoint(world: World) -> int:
    """A checkpoint at the first spot of the checkpoint schedule."""
    x, y = next_spawn(world, "checkpoints")
    return world.create_entity(
        Transform(x=x, y=y),
        Trigger(radius=world.resource(Stage).checkpoints.radius),
        ScoreReward(
            points=world.resource(Rules).scoring.checkpoint,
            label="checkpoint",
        ),
        Respawn(spawner="checkpoints"),
        SpawnedAt(step=world.resource(SimClock).step),
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
