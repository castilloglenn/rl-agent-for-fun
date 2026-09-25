from src.ecs import World
from src.sim.components import PreviousPose, Transform


def pose_history_system(world: World) -> None:
    """Runs first each step: remembers where every car starts the step."""
    for _, (transform, previous) in world.query(Transform, PreviousPose):
        previous.center_x = transform.x
        previous.center_y = transform.y
        previous.angle = transform.angle
