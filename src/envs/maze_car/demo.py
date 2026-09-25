import pygame
from ml_collections import ConfigDict

from src.drivers.registry import make_driver
from src.envs.maze_car.env import MazeCarEnv
from src.sim.resources import Rng
from src.sim.rules import load_rules
from src.utils.timing import FixedStepClock


class MazeCarDemo:
    """Maze Car in a window, driven live by any driver: the keyboard
    (you) by default, or a baseline such as the heuristic.
    """

    def __init__(
        self,
        config: ConfigDict,
        driver: str = "keyboard",
        player: str = "You",
        reward: str = "default",
        round_seconds: float = 0.0,
    ) -> None:
        """round_seconds: above 0, overrides the rules' round length (the
        rules get a new name, so leaderboards don't mix them).
        """
        config = config.copy_and_resolve_references()
        config.show_gui = True  # the demo is always drawn
        self.driver = make_driver(driver, player=player)
        rules = load_rules(config.rules)
        if round_seconds > 0:
            rules = rules.with_round_seconds(round_seconds)
        self.env = MazeCarEnv(
            config,
            driver=self.driver.label,
            random_seeds=True,
            reward=reward,
            rules=rules,
        )
        self.run()

    def run(self) -> None:
        """Fixed-rate simulation steps, drawn at the display's rate."""
        clock = FixedStepClock(self.env.config.sim.steps_per_second)
        world = self.env.world
        self.driver.reset(self._seed())
        elapsed = self.env.render()
        while self.env.running:
            if self.env.world is not world:  # R started a new game
                world = self.env.world
                self.driver.reset(self._seed())
            # Pump first so the key state is current for this frame.
            # Pumping leaves the events queued for the renderer.
            pygame.event.pump()
            for _ in range(clock.advance(elapsed)):
                action = self.driver.act(self.env.last_observation)
                self.env.step_world(action)
            elapsed = self.env.render(clock.alpha)

    def _seed(self) -> int:
        return self.env.world.resource(Rng).seed
