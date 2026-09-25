from src.ecs import World
from src.sim.components import Eliminated, Motion
from src.sim.resources import EventLog, RoundState, SimClock


def round_system(world: World) -> None:
    """Counts the round down, and ends it when time runs out or every
    car is out. Runs last each step.
    """
    state = world.resource(RoundState)
    if state.over:
        return
    step = world.resource(SimClock).step
    log = world.resource(EventLog)

    active = world.query(Motion, exclude=(Eliminated,))
    eliminated = world.query(Eliminated)
    if eliminated and not active:
        state.over, state.reason = True, "all_out"
        log.add(step, "Round over: every car is out", kind="round", danger=True)
        return

    state.steps_left = max(state.steps_left - 1, 0)
    if state.steps_left == 0:
        state.over, state.reason = True, "time"
        log.add(step, "Round over: time up", kind="round")
