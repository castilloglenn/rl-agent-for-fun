from abc import ABC, abstractmethod

import numpy as np


class Environment(ABC):
    """Gymnasium-style environment API (without the dependency)."""

    @abstractmethod
    def reset(self, seed: int | None = None) -> tuple[np.ndarray, dict]:
        """Starts a new episode. Returns (observation, info)."""

    @abstractmethod
    def step(
        self, action: tuple
    ) -> tuple[np.ndarray, float, bool, bool, dict]:
        """Returns (observation, reward, terminated, truncated, info)."""

    @abstractmethod
    def get_state(self) -> np.ndarray:
        """The current observation."""
