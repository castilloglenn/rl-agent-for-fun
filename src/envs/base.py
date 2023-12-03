from abc import ABC, abstractmethod

from src.utils.types import GameOver, Reward, Score


class Environment(ABC):
    @abstractmethod
    def reset(self) -> None:
        pass

    @abstractmethod
    def get_state(self) -> tuple:
        pass

    @abstractmethod
    def game_step(self, action: tuple) -> tuple[Reward, GameOver, Score]:
        pass
