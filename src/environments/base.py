from abc import ABC, abstractmethod

Reward = int | float
GameOver = bool
Score = int | float


class Environment(ABC):

    @abstractmethod
    def reset(self) -> None:
        pass

    @abstractmethod
    def get_state(self) -> tuple:
        pass

    @abstractmethod
    def game_step(self, action) -> tuple[Reward, GameOver, Score]:
        pass
