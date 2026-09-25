"""Spawn schedules: stage + seed decide every spawn, not the driving.

Slot N's candidates depend only on (seed, spawner name, N), so where the
cars drive can't change the sequence. The first candidate far enough from
every car is used, so drivers almost always see identical spawns. See
docs/decisions/009-stage-format-and-spawn-schedules.md.
"""

import math
import random
from dataclasses import dataclass

from src.sim.stage import CheckpointRules

CANDIDATES_PER_SLOT = 8

Point = tuple[float, float]


@dataclass
class SpawnSchedule:
    name: str  # also the random stream name, e.g. "checkpoints"
    seed: int
    rules: CheckpointRules
    width: float
    height: float
    next_slot: int = 0

    def next_spot(self, cars: list[Point]) -> Point:
        slot = self.next_slot
        self.next_slot += 1
        if self.rules.mode == "scripted":
            points = self.rules.points
            return tuple(points[slot % len(points)])  # loops at the end
        candidates = self.candidates(slot)
        for candidate in candidates:
            if all(
                math.dist(candidate, car) >= self.rules.min_car_distance
                for car in cars
            ):
                return candidate
        if not cars:
            return candidates[0]
        return max(  # nothing far enough: the least crowded candidate
            candidates,
            key=lambda c: min(math.dist(c, car) for car in cars),
        )

    def candidates(self, slot: int) -> list[Point]:
        rng = random.Random(f"{self.seed}:{self.name}:{slot}")
        margin = self.rules.border_margin
        return [
            (
                rng.uniform(margin, self.width - margin),
                rng.uniform(margin, self.height - margin),
            )
            for _ in range(CANDIDATES_PER_SLOT)
        ]
