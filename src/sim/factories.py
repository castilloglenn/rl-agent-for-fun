from ml_collections import ConfigDict
from pygame import Rect, Vector2

from src.ecs import World
from src.sim.components import (
    ActionInput,
    CarSpec,
    Hitbox,
    Motion,
    PreviousPose,
    Ray,
    Renderable,
    Sensors,
    Transform,
)
from src.sim.resources import Field, SimClock, SimConfig
from src.sim.systems import SIMULATION_SYSTEMS
from src.sim.systems.sensors import cast_rays
from src.utils.types import Colors, ColorValue


def create_world(config: ConfigDict) -> World:
    world = World()
    world.add_resource(SimConfig.from_config(config))
    world.add_resource(Field.from_config(config))
    world.add_resource(SimClock())
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
) -> int:
    config = world.resource(SimConfig)

    # Matches the pre-ECS Car: Rect truncates x/y, and they are then used
    # as the center, not the top-left.
    spec_rect = Rect(x, y, width, height)
    rect = Rect(0, 0, spec_rect.width, spec_rect.height)
    rect.center = (spec_rect.x, spec_rect.y)

    transform = Transform()
    hitbox = Hitbox(width=spec_rect.width, height=spec_rect.height, rect=rect)
    sensors = Sensors(
        rays=[
            Ray("front", angle=0, offset=rect.width // 2),
            Ray(
                "left",
                angle=30,
                offset=Vector2(rect.topright).distance_to(
                    Vector2(rect.center)
                ),
            ),
            Ray(
                "right",
                angle=-30,
                offset=Vector2(rect.bottomright).distance_to(
                    Vector2(rect.center)
                ),
            ),
            Ray("back", angle=180, offset=rect.width // 2),
        ]
    )
    cast_rays(
        sensors,
        hitbox.rect,
        transform.angle,
        world.resource(Field),
        config.ray_length,
    )

    return world.create_entity(
        ActionInput(),
        transform,
        Motion(),
        _car_spec(config),
        hitbox,
        sensors,
        PreviousPose(*rect.center, transform.angle),
        Renderable(color=color, label=label),
    )


def create_start_car(
    world: World,
    color: ColorValue = Colors.SKY_BLUE,
    label: str = "Car 1",
) -> int:
    """A car at the pre-ECS starting position: left quarter, mid height."""
    field = world.resource(Field)
    config = world.resource(SimConfig)
    return create_car(
        world,
        x=field.quarter_width - config.car_width // 2,
        y=field.half_height - config.car_height // 2,
        width=config.car_width,
        height=config.car_height,
        color=color,
        label=label,
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
    )
