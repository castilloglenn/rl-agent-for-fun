"""Spawn schedules: stage + seed decide every spawn, not the driving.

Slot N's candidates depend only on (seed, spawner name, N), so where the
cars drive can't change the sequence. The first candidate far enough from
every car is used, so drivers almost always see identical spawns. See
docs/decisions/009-stage-format-and-spawn-schedules.md.

With walls (step 7a), a candidate too close to a wall (closer than the
border margin) is skipped, and more candidates follow the first 8 when
walls reject them all. Without walls nothing changes.
"""

import math
import random
from dataclasses import dataclass

from src.sim.stage import FuelRules

CANDIDATES_PER_SLOT = 8
MAX_CANDIDATES = 64  # when walls reject the first ones

Point = tuple[float, float]


@dataclass
class SpawnSchedule:
    name: str  # also the random stream name: "fuel"
    seed: int
    rules: FuelRules
    width: float
    height: float
    next_slot: int = 0
    walls: tuple = ()  # walls.Box: candidates keep clear of them

    def next_spot(
        self, cars: list[Point], others: list[Point] = ()
    ) -> Point:
        """The next spot. Random: clear of the cars and of the other
        fuels out (`others`, 9a2), as far as the candidates allow.
        """
        slot = self.next_slot
        self.next_slot += 1
        if self.rules.mode == "scripted":
            points = self.rules.points
            # Loops at the end; a "seeded" start begins at a point picked
            # from the seed (7d5a), the same for every driver.
            first = 0
            if self.rules.start == "seeded":
                rng = random.Random(f"{self.seed}:{self.name}:start")
                first = rng.randrange(len(points))
            return tuple(points[(slot + first) % len(points)])
        candidates = self.candidates(slot)
        near = list(cars) + list(others)
        for candidate in candidates:
            if all(
                math.dist(candidate, spot) >= self.rules.min_car_distance
                for spot in near
            ):
                return candidate
        if not near:
            return candidates[0]
        return max(  # nothing far enough: the least crowded candidate
            candidates,
            key=lambda c: min(math.dist(c, spot) for spot in near),
        )

    def candidates(self, slot: int) -> list[Point]:
        """The slot's candidate spots, clear of walls. The first 8 draws
        are always the same (so a stage without walls is unchanged);
        more are drawn only when walls reject all of those.
        """
        rng = random.Random(f"{self.seed}:{self.name}:{slot}")
        margin = self.rules.border_margin

        def draw() -> Point:
            return (
                rng.uniform(margin, self.width - margin),
                rng.uniform(margin, self.height - margin),
            )

        drawn = [draw() for _ in range(CANDIDATES_PER_SLOT)]
        if not self.walls:
            return drawn
        clear = [p for p in drawn if self._clear(p)]
        while not clear and len(drawn) < MAX_CANDIDATES:
            point = draw()
            drawn.append(point)
            if self._clear(point):
                clear.append(point)
        return clear or drawn[:1]  # nowhere clear: the stage is too full

    def _clear(self, point: Point) -> bool:
        margin = self.rules.border_margin
        return all(box.distance(*point) >= margin for box in self.walls)
