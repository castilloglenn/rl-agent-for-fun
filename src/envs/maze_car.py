from src.envs.base import Environment, GameOver, Reward, Score


class MazeCarEnv(Environment):
    def __init__(self, user_inputs: bool = False) -> None:
        self.user_inputs = user_inputs
        print("MazeCarEnv")

    def reset(self) -> None:
        pass

    def get_state(self) -> tuple:
        pass

    def game_step(self, action) -> tuple[Reward, GameOver, Score]:
        pass
