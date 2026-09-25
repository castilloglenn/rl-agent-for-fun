from src.ecs import World
from src.sim.elimination import round_active
from src.sim.resources import SimClock


def clock_system(world: World) -> None:
    if round_active(world):
        world.resource(SimClock).step += 1
