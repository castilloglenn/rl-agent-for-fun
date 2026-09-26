import math

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
from src.sim.collisions import end_scrape, hit_wall, scrape_wall
from src.sim.elimination import round_active
from src.sim.geometry import car_corners, impact_speed, move_until_contact
from src.sim.resources import Field, SimConfig
from src.utils.common import get_angular_movement_deltas


def movement_system(world: World) -> None:
    if not round_active(world):
        return
    field = world.resource(Field)
    steps_per_second = world.resource(SimConfig).steps_per_second
    for car, (action, transform, motion, spec, hitbox) in world.query(
        ActionInput, Transform, Motion, CarSpec, Hitbox, exclude=(Eliminated,)
    ):
        motion.speed, motion.pedal = next_speed(motion.speed, action, spec)
        delta_x, delta_y = get_angular_movement_deltas(
            angle=transform.angle, speed=motion.speed
        )
        start = (transform.x, transform.y)
        forward = 1.0 if motion.speed >= 0 else -1.0
        fraction, hit_x, hit_y = _move(
            delta_x, delta_y, transform, hitbox, field
        )
        motion.moved = motion.speed * fraction
        if fraction < 1.0:
            impact = impact_speed(delta_x, delta_y, hit_x, hit_y)
            # Slide: keep the motion along the wall, lose the part into it.
            slide_x = 0.0 if hit_x else delta_x * (1 - fraction)
            slide_y = 0.0 if hit_y else delta_y * (1 - fraction)
            along = math.hypot(slide_x, slide_y) / (
                math.hypot(delta_x, delta_y) * (1 - fraction) or 1.0
            )
            hit_wall(world, car, impact * steps_per_second, keep=along)
            if along and not world.try_component(car, Eliminated):
                before = (transform.x, transform.y)
                if _move(slide_x, slide_y, transform, hitbox, field)[0] < 1:
                    motion.speed = 0.0  # into a corner: stopped there
                slid = math.dist(before, (transform.x, transform.y))
                scrape_wall(world, car, slid)
            moved = math.hypot(transform.x - start[0], transform.y - start[1])
            motion.moved = forward * moved
        if not world.try_component(car, Eliminated):
            end_scrape(world, car)


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
) -> tuple[float, bool, bool]:
    """Moves as far as possible until a corner touches the border.
    Returns the fraction of the move made (below 1 means it touched a
    wall), and which borders stopped it (left/right, top/bottom).
    """
    corners = car_corners(
        transform.x, transform.y, transform.angle, hitbox.width, hitbox.height
    )
    fraction, hit_x, hit_y = move_until_contact(corners, dx, dy, field.rect)
    transform.x += dx * fraction
    transform.y += dy * fraction
    return fraction, hit_x, hit_y
