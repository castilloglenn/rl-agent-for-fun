from src.ecs import World
from src.sim.components import Hitbox, PreviousPose, Transform


def pose_history_system(world: World) -> None:
    """Runs first each step: remembers where every car starts the step."""
    for _, (transform, hitbox, previous) in world.query(
        Transform, Hitbox, PreviousPose
    ):
        previous.center_x, previous.center_y = hitbox.rect.center
        previous.angle = transform.angle
