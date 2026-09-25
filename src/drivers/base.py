from abc import ABC, abstractmethod

import numpy as np

from src.drivers.actions import Action


class Driver(ABC):
    """Decides a car's action from its observation, one step at a time.

    Every driver (keyboard, baselines, RL and imitation agents) implements
    this, so nothing downstream needs special cases.
    """

    #: Shown in the HUD and used in the driver record.
    name: str = "driver"

    def reset(self, seed: int | None = None) -> None:
        """A new game starts. Drivers with randomness reseed here."""

    @abstractmethod
    def act(self, observation: np.ndarray) -> Action:
        """5 bools, in the env's action_names order."""

    def record(self) -> dict:
        """This driver's record for replays and runs."""
        return {"type": "baseline", "id": self.name}

    @property
    def label(self) -> str:
        """How the HUD names this driver."""
        return f"{self.name} (baseline)"
