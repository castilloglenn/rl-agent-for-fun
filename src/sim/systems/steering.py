from src.ecs import World
from src.sim.components import ActionInput, CarSpec, Hitbox, Motion, Transform
from src.sim.geometry import rotated_bounds
from src.sim.resources import Field


def steering_system(world: World) -> None:
    field = world.resource(Field)
    for _, (action, transform, motion, spec, hitbox) in world.query(
        ActionInput, Transform, Motion, CarSpec, Hitbox
    ):
        turn = turn_step(action, motion.speed, spec)
        if not turn:
            continue

        transform.angle = (transform.angle + turn) % 360
        hitbox.rect = rotated_bounds(
            hitbox.width, hitbox.height, transform.angle, hitbox.rect.center
        )
        hitbox.rect.clamp_ip(field.rect)


def turn_step(action: ActionInput, speed: float, spec: CarSpec) -> float:
    """Degrees to turn this step. Positive is counterclockwise.

    The turn rate follows speed, up to the max at full_turn_speed, so a
    stopped car can't turn. Steering flips while rolling backward.
    """
    steer = int(action.turn_left) - int(action.turn_right)
    if not steer or speed == 0:
        return 0.0
    grip = min(abs(speed) / spec.full_turn_speed, 1.0)
    direction = 1 if speed > 0 else -1
    return steer * direction * spec.max_turn_rate * grip
