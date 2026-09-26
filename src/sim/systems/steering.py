from src.ecs import World
from src.sim.components import (
    ActionInput,
    CarSpec,
    Eliminated,
    Hitbox,
    Motion,
    Transform,
)
from src.sim.collisions import hit_wall
from src.sim.elimination import round_active
from src.sim.geometry import car_corners, inside, rotation_impact
from src.sim.resources import Field, SimConfig


def steering_system(world: World) -> None:
    if not round_active(world):
        return
    field = world.resource(Field)
    for car, (action, transform, motion, spec, hitbox) in world.query(
        ActionInput, Transform, Motion, CarSpec, Hitbox, exclude=(Eliminated,)
    ):
        motion.steering = next_steering(motion.steering, action, spec)
        turn = turn_step(motion.steering, motion.speed, spec)
        if not turn:
            continue

        angle = (transform.angle + turn) % 360
        corners = car_corners(
            transform.x, transform.y, angle, hitbox.width, hitbox.height
        )
        if inside(corners, field.rect):
            transform.angle = angle
            continue
        # Turning a corner into the border is a wall hit: the turn is
        # blocked (the speed stays), and the corner's speed into the wall
        # is the impact.
        before = car_corners(
            transform.x,
            transform.y,
            transform.angle,
            hitbox.width,
            hitbox.height,
        )
        impact = rotation_impact(before, corners, field.rect)
        steps_per_second = world.resource(SimConfig).steps_per_second
        hit_wall(world, car, impact * steps_per_second, keep=1.0)


def next_steering(steering: float, action: ActionInput, spec: CarSpec) -> float:
    """Moves the steering wheel one step toward the pressed direction.

    Like a real wheel, it takes time to reach full lock (steer_rate) and
    self-centers faster (steer_return_rate). Switching sides passes
    through center. Left and right together count as no steering.
    """
    target = int(action.turn_left) - int(action.turn_right)
    heading_to_center = (steering > 0 and target <= 0) or (
        steering < 0 and target >= 0
    )
    if heading_to_center:
        if steering > 0:
            return max(steering - spec.steer_return_rate, 0.0)
        return min(steering + spec.steer_return_rate, 0.0)
    if target > 0:
        return min(steering + spec.steer_rate, 1.0)
    if target < 0:
        return max(steering - spec.steer_rate, -1.0)
    return steering


def turn_step(steering: float, speed: float, spec: CarSpec) -> float:
    """Degrees to turn this step. Positive is counterclockwise.

    The turn rate follows the wheel position, and speed up to the max at
    full_turn_speed, so a stopped car can't turn. Steering flips while
    rolling backward.
    """
    if not steering or speed == 0:
        return 0.0
    grip = min(abs(speed) / spec.full_turn_speed, 1.0)
    direction = 1 if speed > 0 else -1
    return steering * direction * spec.max_turn_rate * grip
