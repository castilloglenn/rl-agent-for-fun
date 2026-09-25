from src.ecs import World
from src.sim.components import ActionInput, CarSpec, Hitbox, Motion, Transform
from src.sim.geometry import rotated_bounds
from src.sim.resources import Field, SimConfig


def steering_system(world: World) -> None:
    config = world.resource(SimConfig)
    field = world.resource(Field)
    for _, (action, transform, motion, spec, hitbox) in world.query(
        ActionInput, Transform, Motion, CarSpec, Hitbox
    ):
        direction = _turn_direction(action)
        if not direction:
            continue

        # Turn rate scales with acceleration, with a floor so a stopped
        # car can still turn slowly.
        adjusted = (direction * spec.turn_speed) * max(
            motion.acceleration_rate, config.acceleration_unit
        )
        transform.angle = (transform.angle + adjusted) % 360
        hitbox.rect = rotated_bounds(
            hitbox.width, hitbox.height, transform.angle, hitbox.rect.center
        )
        hitbox.rect.clamp_ip(field.rect)


def _turn_direction(action: ActionInput) -> int:
    """+1 turns counterclockwise. Steering flips while reversing."""
    if action.turn_left:
        return -1 if action.move_backward else 1
    if action.turn_right:
        return 1 if action.move_backward else -1
    return 0
