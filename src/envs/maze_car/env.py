from typing import Optional

from ml_collections import ConfigDict

from src.envs.base import Environment
from src.render.renderer import Renderer
from src.sim.components import ActionInput
from src.sim.factories import create_start_car, create_world
from src.utils.types import GameOver, Reward, Score


class MazeCarEnv(Environment):
    """Wraps a simulation World. Renders it when config.show_gui is on."""

    def __init__(self, config: ConfigDict, driver: str = "Agent") -> None:
        self.config = config
        self.driver = driver  # shown in the HUD
        self.renderer: Renderer | None = (
            Renderer(config) if config.show_gui else None
        )
        self.reset()

    def reset(self) -> None:
        self.world = create_world(self.config)
        self.car = create_start_car(self.world, label=self.driver)
        self.score: int | float = 0
        self.is_game_over: bool = False
        self.running: bool = True

    def get_state(self) -> tuple:
        pass

    def game_step(
        self, action: Optional[tuple] = None
    ) -> tuple[Reward, GameOver, Score]:
        """One simulation step, then one frame if the GUI is on.

        action: (turn_left, turn_right, gas, reverse, brake).
        """
        result = self.step_world(action)
        if self.renderer:
            self.render()
        return result

    def step_world(
        self, action: Optional[tuple] = None
    ) -> tuple[Reward, GameOver, Score]:
        """One simulation step, without drawing."""
        action_input = ActionInput(*action) if action else ActionInput()
        self.world.add_component(self.car, action_input)
        self.world.step()

        reward: int | float = self._calculate_reward()
        game_over: bool = False

        return (reward, game_over, self.score)

    def render(self, alpha: float = 1.0) -> float:
        """Handles window events and draws one frame. Returns the real
        seconds since the previous frame.
        """
        if self.renderer.poll_events():
            self.running = False
        self.renderer.draw(self.world, alpha)
        return self.renderer.present()

    def _calculate_reward(self) -> int | float:
        return 0
