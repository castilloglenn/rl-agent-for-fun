"""The fuel tank (step 9a2): every throttle and turn burns fuel, and an
empty tank ends a car's round. Runs first each step, before the controls
move the car.

- **Burn:** the rules' `tank` rates per second: idle always, more with
  gas or reverse held, more while turning; braking burns nothing.
- **Empty:** the engine is dead. The controls do nothing (the car
  coasts, its drag slowing it), and once it has stopped it's out of the
  round ("out_of_fuel"). Rolling into a fuel on the way refills it, and
  the engine runs again.
"""

from src.ecs import World
from src.sim.components import ActionInput, Eliminated, Motion, Tank
from src.sim.elimination import eliminate, round_active
from src.sim.resources import EventLog, SimClock, SimConfig
from src.sim.rules import Rules

OUT_OF_FUEL = "out_of_fuel"


def tank_system(world: World) -> None:
    if not round_active(world):
        return
    rules = world.resource(Rules).tank
    if rules is None:
        return
    seconds = 1.0 / world.resource(SimConfig).steps_per_second
    for car, (tank, action, motion) in world.query(
        Tank, ActionInput, Motion, exclude=(Eliminated,)
    ):
        tank.burned = 0.0
        if tank.empty:
            if motion.speed == 0.0:  # coasted to a stop: out
                eliminate(world, car, OUT_OF_FUEL)
                continue
            _dead_engine(action)
            continue
        burn = rules.burn(
            throttle=action.gas or action.reverse,
            steering=action.turn_left or action.turn_right,
        )
        tank.burned = min(burn * seconds, tank.level)
        tank.level -= tank.burned
        if tank.empty:
            tank.level = 0.0
            world.resource(EventLog).add(
                world.resource(SimClock).step,
                "Out of fuel: the engine stops",
                kind="fuel",
                danger=True,
            )


def _dead_engine(action: ActionInput) -> None:
    """No gas, reverse, brake, or steering: the car only coasts."""
    action.turn_left = action.turn_right = False
    action.gas = action.reverse = action.brake = False
