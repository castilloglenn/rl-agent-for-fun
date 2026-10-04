"""The navigator (roadmap 7f12, decision 069): a hand-written teacher that
uses what agents can sense now, to record for cloning. The heuristic
stays the 1.0 bar every skill is measured against; this is not scored.

Unlike the heuristic it:
- steers at the remembered route's waypoint (7f7), not straight at the
  fuel, so it goes around walls;
- judges the way ahead with the narrow front rays (0 and 15 degrees), so
  it drives through gaps the heuristic's 45-degree rays turn it away from;
- backs out when the stuck timer says it's been stuck a while.
"""

import numpy as np

from src.drivers.actions import Action
from src.drivers.base import Driver
from src.sim.observation import OBSERVATION_NAMES

_INDEX = {name: i for i, name in enumerate(OBSERVATION_NAMES)}


class Navigator(Driver):
    name = "navigator"

    def __init__(
        self,
        aim_cos: float = 0.97,  # steer unless the waypoint is this far ahead
        wall_margin: float = 0.03,  # px / 980: a wall this close ahead
        side_margin: float = 0.015,  # a side wall this close: ease off it
        corner_speed: float = 0.45,  # speed cap while turning hard
        approach_speed: float = 0.3,  # near an off-center fuel
        behind_speed: float = 0.15,  # the waypoint behind: turn slowly
        stuck_after: float = 0.2,  # the stuck input (2 s): back out
        back_out_steps: int = 90,  # 0.75 s of reverse
    ) -> None:
        self.aim_cos = aim_cos
        self.wall_margin = wall_margin
        self.side_margin = side_margin
        self.corner_speed = corner_speed
        self.approach_speed = approach_speed
        self.behind_speed = behind_speed
        self.stuck_after = stuck_after
        self.back_out_steps = back_out_steps
        self.reset()

    def reset(self, seed: int | None = None) -> None:
        self._backing = 0  # steps of backing out left
        self._back_steer = 0

    def act(self, observation: np.ndarray) -> Action:
        o = {name: float(observation[i]) for name, i in _INDEX.items()}
        speed = o["speed"]
        front = min(o["ray_front"], o["ray_front_left_15"],
                    o["ray_front_right_15"])
        left_room = o["ray_front_left_30"] + o["ray_front_left"]
        right_room = o["ray_front_right_30"] + o["ray_front_right"]

        # Stuck for a while against something: back out, swinging the
        # front toward the waypoint.
        if self._backing == 0 and o["stuck"] >= self.stuck_after and (
            front < 0.08
        ):
            self._backing = self.back_out_steps
            # Reversing with the wheel turned swings the front the other
            # way: steer away from the waypoint's side, so it ends up
            # facing the waypoint.
            self._back_steer = -1 if o["route_sin"] > 0 else 1
        if self._backing:
            self._backing -= 1
            steer = self._back_steer
            return (steer > 0, steer < 0, False, True, False)

        # Steer toward the waypoint (sin > 0: it's to the left).
        steer = 0
        if o["route_cos"] < self.aim_cos:
            steer = 1 if o["route_sin"] > 0 else -1

        # A wall close ahead wins: turn toward the waypoint's side if it
        # has some room, else toward the side with more.
        stopping = 0.16 * speed * speed + 0.08 * speed
        if front < self.wall_margin + stopping:
            wanted = 1 if o["route_sin"] > 0 else -1
            room = left_room if wanted > 0 else right_room
            if room < 0.12:
                wanted = 1 if left_room > right_room else -1
            steer = wanted
        # Scraping a side: ease away from it.
        elif o["ray_front_left"] < self.side_margin:
            steer = -1
        elif o["ray_front_right"] < self.side_margin:
            steer = 1

        speed_cap = 1.0
        if o["route_cos"] < 0.5:
            speed_cap = self.corner_speed
        if o["route_cos"] < 0:  # behind: a tight turn
            speed_cap = self.behind_speed
        near = o["fuel_distance"] < 0.15
        if near and o["fuel_cos"] < self.aim_cos:
            speed_cap = min(speed_cap, self.approach_speed)
        if o["ray_front"] < 0.02 + stopping and speed > 0.05:
            pedal = "brake"
        elif speed > speed_cap + 0.1:
            pedal = "brake"
        elif speed > speed_cap:
            pedal = "none"
        else:
            pedal = "gas"
        return (steer > 0, steer < 0, pedal == "gas", False, pedal == "brake")
