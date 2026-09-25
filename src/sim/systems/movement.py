from src.ecs import World
from src.sim.components import (
    ActionInput,
    CarSpec,
    Hitbox,
    Motion,
    Pedal,
    Transform,
)
from src.sim.resources import Field
from src.utils.common import get_angular_movement_deltas, get_clamped_rect


def movement_system(world: World) -> None:
    field = world.resource(Field)
    for _, (action, transform, motion, spec, hitbox) in world.query(
        ActionInput, Transform, Motion, CarSpec, Hitbox
    ):
        motion.speed, motion.pedal = next_speed(motion.speed, action, spec)
        delta_x, delta_y = get_angular_movement_deltas(
            angle=transform.angle, speed=motion.speed
        )
        _move(delta_x, delta_y, transform, motion, hitbox, field)


def next_speed(
    speed: float, action: ActionInput, spec: CarSpec
) -> tuple[float, str]:
    """Applies one step of pedal input to the signed speed.

    Brake beats gas, and gas beats reverse. Gas while rolling backward and
    reverse while rolling forward both brake first, like a real car.
    """
    if action.brake:
        return _toward_zero(speed, spec.brake_deceleration), Pedal.BRAKING
    if action.gas:
        if speed < 0:
            return _toward_zero(speed, spec.brake_deceleration), Pedal.BRAKING
        return min(speed + spec.acceleration, spec.max_speed), Pedal.GAS
    if action.reverse:
        if speed > 0:
            return _toward_zero(speed, spec.brake_deceleration), Pedal.BRAKING
        return (
            max(speed - spec.reverse_acceleration, -spec.max_reverse_speed),
            Pedal.REVERSE,
        )
    if speed == 0:
        return 0.0, Pedal.IDLE
    return _toward_zero(speed, spec.drag), Pedal.COASTING


def _toward_zero(speed: float, amount: float) -> float:
    if speed > 0:
        return max(speed - amount, 0.0)
    return min(speed + amount, 0.0)


def _move(
    x: float,
    y: float,
    transform: Transform,
    motion: Motion,
    hitbox: Hitbox,
    field: Field,
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

    # The border stops the car until crashes arrive (roadmap step 3f).
    if is_clamped:
        motion.speed = 0.0
