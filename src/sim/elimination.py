"""One way for a car to leave a round, shared by every cause: walls now,
hazards and weapons later (see docs/game-design.md, hazards).
"""

from src.ecs import World
from src.sim.components import Eliminated, Motion, Renderable
from src.sim.resources import EventLog, RoundState, SimClock

REASON_TEXT = {"wrecked": "was wrecked"}


def eliminate(world: World, car: int, reason: str) -> None:
    if world.try_component(car, Eliminated):
        return
    step = world.resource(SimClock).step
    world.add_component(car, Eliminated(reason=reason, step=step))
    world.component(car, Motion).speed = 0.0

    renderable = world.try_component(car, Renderable)
    name = renderable.label if renderable else f"Car {car}"
    what = REASON_TEXT.get(reason, f"was eliminated ({reason})")
    world.resource(EventLog).add(
        step, f"{name} {what}", kind="elimination", danger=True
    )


def round_active(world: World) -> bool:
    """False once the round is over: the world then stays frozen."""
    return not world.resource(RoundState).over
