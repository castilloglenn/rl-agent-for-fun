import random
from typing import Optional

from ml_collections import ConfigDict

from src.envs.base import Environment
from src.render.renderer import Command, Renderer
from src.sim.components import ActionInput
from src.sim.components import Score as CarScore
from src.sim.factories import create_game
from src.sim.resources import RoundState
from src.utils.types import GameOver, Reward, Score


class MazeCarEnv(Environment):
    """Wraps a simulation World. Renders it when config.show_gui is on."""

    def __init__(
        self,
        config: ConfigDict,
        driver: str = "Agent",
        random_seeds: bool = False,
    ) -> None:
        """random_seeds: pick a fresh seed on every reset (the demo), rather
        than `game.seed` (agents and tests, for repeatable rounds).
        """
        self.config = config
        self.driver = driver  # shown in the HUD
        self.random_seeds = random_seeds
        self.renderer: Renderer | None = (
            Renderer(config) if config.show_gui else None
        )
        self.reset()

    def reset(self, seed: int | None = None) -> None:
        if seed is None and self.random_seeds:
            seed = random.SystemRandom().randrange(1_000_000)
        self.world, self.car = create_game(
            self.config, label=self.driver, seed=seed
        )
        self.running: bool = True

    @property
    def score(self) -> float:
        return self.world.component(self.car, CarScore).total

    @property
    def is_game_over(self) -> bool:
        return self.world.resource(RoundState).game_over

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
        """One simulation step, without drawing. Does nothing once the
        game is over.
        """
        if self.is_game_over:
            return (0, True, self.score)
        action_input = ActionInput(*action) if action else ActionInput()
        self.world.add_component(self.car, action_input)
        self.world.step()

        reward = self.world.component(self.car, CarScore).last_step
        return (reward, self.is_game_over, self.score)

    def render(self, alpha: float = 1.0) -> float:
        """Handles window events and draws one frame. Returns the real
        seconds since the previous frame.
        """
        commands = self.renderer.poll_events()
        if Command.QUIT in commands:
            self.running = False
        if Command.RESTART in commands:
            self.reset()
        self.renderer.draw(self.world, alpha)
        return self.renderer.present()
