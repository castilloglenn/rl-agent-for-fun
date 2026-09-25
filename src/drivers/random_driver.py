import random

from src.drivers.actions import CANONICAL_ACTIONS, Action
from src.drivers.base import Driver


class RandomDriver(Driver):
    """Random canonical actions, re-chosen every `decision_interval` steps
    (4 steps = 30 decisions/s at 120 steps/s, like agents). The floor every
    trained agent must beat.
    """

    name = "random"

    def __init__(self, seed: int = 0, decision_interval: int = 4) -> None:
        self.seed = seed
        self.decision_interval = decision_interval
        self.reset(seed)

    def reset(self, seed: int | None = None) -> None:
        if seed is not None:
            self.seed = seed
        self._rng = random.Random(f"{self.seed}:random-driver")
        self._steps = 0
        self._action = CANONICAL_ACTIONS[0]

    def act(self, observation=None) -> Action:
        if self._steps % self.decision_interval == 0:
            self._action = self._rng.choice(CANONICAL_ACTIONS)
        self._steps += 1
        return self._action

    def record(self) -> dict:
        return {"type": "baseline", "id": self.name, "seed": self.seed}
