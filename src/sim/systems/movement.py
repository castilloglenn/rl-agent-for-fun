from src.ecs import World
from src.sim.components import (
    ActionInput,
    CarSpec,
    Eliminated,
    Hitbox,
    Motion,
    Pedal,
    Transform,
)
from src.sim.elimination import eliminate, round_active
from src.sim.geometry import car_corners, max_move_fraction
from src.sim.resources import Field
from src.utils.common import get_angular_movement_deltas


def movement_system(world: World) -> None:
    if not round_active(world):
        return
    field = world.resource(Field)
    for car, (action, transform, motion, spec, hitbox) in world.query(
        ActionInput, Transform, Motion, CarSpec, Hitbox, exclude=(Eliminated,)
    ):
        motion.speed, motion.pedal = next_speed(motion.speed, action, spec)
        delta_x, delta_y = get_angular_movement_deltas(
            angle=transform.angle, speed=motion.speed
        )
        fraction = _move(delta_x, delta_y, transform, hitbox, field)
        motion.moved = motion.speed * fraction
        if fraction < 1.0:
            eliminate(world, car, "wall")


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
    dx: float,
    dy: float,
    transform: Transform,
    hitbox: Hitbox,
    field: Field,
) -> float:
    """Moves as far as possible until a corner touches the border.
    Returns the fraction of the move made: below 1 means it touched (a
    crash).
    """
    corners = car_corners(
        transform.x, transform.y, transform.angle, hitbox.width, hitbox.height
    )
    fraction = max_move_fraction(corners, dx, dy, field.rect)
    transform.x += dx * fraction
    transform.y += dy * fraction

    return fraction
