from src.ecs import World
from src.sim.resources import SimClock


def clock_system(world: World) -> None:
    world.resource(SimClock).step += 1
