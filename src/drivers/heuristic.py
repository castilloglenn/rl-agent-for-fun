import numpy as np

from src.drivers.actions import Action
from src.drivers.base import Driver
from src.sim.observation import NO_FUEL, OBSERVATION_NAMES, fuel_slots

_INDEX = {name: i for i, name in enumerate(OBSERVATION_NAMES)}


class CompassDriver(Driver):
    """Hand-written rules on the observation only, like an agent sees it:
    steer toward the fuel with the compass, turn away from close
    walls, and brake when the wall ahead is within stopping range. Of the
    fuels out, it goes for the nearest in a straight line (9b).

    Distances are fractions of the observation's distance scale (the
    box's diagonal, about 980 px, on every map), speed a fraction of max
    speed (see docs/game-design.md, Observation).
    """

    name = "heuristic"

    def __init__(
        self,
        aim_cos: float = 0.95,  # steer unless the fuel is this dead ahead
        wall_margin: float = 0.05,  # turn away from walls closer than this
        brake_margin: float = 0.03,  # plus the stopping distance: brake
        corner_speed: float = 0.5,  # speed cap while turning hard
        approach_distance: float = 0.15,  # a fuel this close is "near"
        approach_speed: float = 0.25,  # speed cap near an off-center fuel
    ) -> None:
        self.aim_cos = aim_cos
        self.wall_margin = wall_margin
        self.brake_margin = brake_margin
        self.corner_speed = corner_speed
        self.approach_distance = approach_distance
        self.approach_speed = approach_speed

    def act(self, observation: np.ndarray) -> Action:
        o = {name: float(observation[i]) for name, i in _INDEX.items()}
        speed = o["speed"]
        front = o["ray_front"]
        front_left, front_right = o["ray_front_left"], o["ray_front_right"]

        fuel = min(
            fuel_slots(o), key=lambda f: f["distance"], default=NO_FUEL
        )
        # Steer toward the fuel (sin > 0: it's to the left).
        steer = 0
        if fuel["cos"] < self.aim_cos:
            steer = 1 if fuel["sin"] > 0 else -1

        # Walls close ahead win: turn toward the side with more room.
        stopping = 0.16 * speed * speed + 0.08 * speed  # about 150 px at max
        wall_ahead = min(front, front_left, front_right)
        if wall_ahead < self.wall_margin + stopping:
            steer = 1 if front_left > front_right else -1

        # Pedals: brake when the wall ahead is within stopping range, and
        # slow down for sharp turns and for a near fuel that isn't
        # dead ahead: a slower car turns tighter, instead of orbiting it.
        speed_cap = 1.0
        if fuel["cos"] < 0.5:
            speed_cap = self.corner_speed
        near = fuel["distance"] < self.approach_distance
        if near and fuel["cos"] < self.aim_cos:
            speed_cap = min(speed_cap, self.approach_speed)
        if front < self.brake_margin + stopping and speed > 0.05:
            pedal = "brake"
        elif speed > speed_cap + 0.1:
            pedal = "brake"
        elif speed > speed_cap:
            pedal = "none"
        else:
            pedal = "gas"

        return (
            steer > 0,
            steer < 0,
            pedal == "gas",
            False,
            pedal == "brake",
        )
