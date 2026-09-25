import pygame

from src.ecs import World
from src.sim.components import ActionInput, CarSpec, Hitbox, Motion, Transform
from src.sim.resources import Field, SimConfig
from src.utils.common import get_angular_movement_deltas, get_clamped_rect


def movement_system(world: World) -> None:
    config = world.resource(SimConfig)
    field = world.resource(Field)
    for _, (action, transform, motion, spec, hitbox) in world.query(
        ActionInput, Transform, Motion, CarSpec, Hitbox
    ):
        if action.move_forward:
            _forward(transform, motion, spec, hitbox, field, config)
        elif action.move_backward:
            _backward(transform, motion, spec, hitbox, field, config)

        if not action.is_moving:
            _set_speed(motion, 0, 0.0, config)


def _forward(transform, motion, spec, hitbox, field, config) -> None:
    # The boost is largest at low acceleration, so the car starts quickly.
    acc_rel = motion.acceleration_rate / config.acceleration_max
    boost = spec.acceleration_unit / max(acc_rel, 0.01)
    rate = motion.acceleration_rate + boost
    _set_speed(motion, spec.forward_speed * rate, rate, config)
    delta_x, delta_y = get_angular_movement_deltas(
        angle=transform.angle, speed=motion.speed
    )
    _move(delta_x, delta_y, transform, motion, hitbox, field, config)


def _backward(transform, motion, spec, hitbox, field, config) -> None:
    _set_speed(motion, spec.backward_speed, 0.0, config)
    delta_x, delta_y = get_angular_movement_deltas(
        angle=transform.angle, speed=motion.speed
    )
    _move(-delta_x, -delta_y, transform, motion, hitbox, field, config)


def _move(
    x: float,
    y: float,
    transform: Transform,
    motion: Motion,
    hitbox: Hitbox,
    field: Field,
    config: SimConfig,
) -> None:
    transform.x_float += x - int(x)
    transform.y_float += y - int(y)

    x_adjusted = int(x) + int(transform.x_float)
    y_adjusted = int(y) + int(transform.y_float)

    is_clamped, hitbox.rect = get_clamped_rect(
        rect=hitbox.rect,
        constraint=field.rect,
        new_x=x_adjusted,
        new_y=y_adjusted,
    )

    transform.x_float -= int(transform.x_float)
    transform.y_float -= int(transform.y_float)

    if is_clamped:
        _set_speed(motion, 0, 0.0, config)


def _set_speed(
    motion: Motion, speed: float, acceleration_rate: float, config: SimConfig
) -> None:
    motion.acceleration_rate = pygame.math.clamp(
        acceleration_rate, 0.0, config.acceleration_max
    )
    motion.speed = speed
