import random
from typing import Optional

import numpy as np
from ml_collections import ConfigDict

from src.envs.base import Environment
from src.envs.maze_car.rewards import (
    RewardProfile,
    StepEvents,
    load_reward_profile,
)
from src.render.renderer import Command, Renderer
from src.sim.components import ActionInput, Eliminated, Motion
from src.sim.components import Score as CarScore
from src.sim.factories import create_game
from src.sim.observation import (
    OBSERVATION_NAMES,
    OBSERVATION_VERSION,
    observe,
)
from src.sim.resources import RoundState, SimClock, SimConfig
from src.sim.systems.sensors import RAY_LAYOUT
from src.utils.types import GameOver, Reward, Score

ACTION_NAMES = ("turn_left", "turn_right", "gas", "reverse", "brake")
RAY_COUNT = len(RAY_LAYOUT)  # the observation starts with the rays


class MazeCarEnv(Environment):
    """Wraps a simulation World. Renders it when config.show_gui is on.

    Agents use the Gymnasium-style `reset(seed)` and `step(action)`.
    The demo uses `step_world` and `render` in its real-time loop.
    """

    observation_names = OBSERVATION_NAMES
    observation_version = OBSERVATION_VERSION
    action_names = ACTION_NAMES

    def __init__(
        self,
        config: ConfigDict,
        driver: str = "Agent",
        random_seeds: bool = False,
        reward: str | RewardProfile = "default",
    ) -> None:
        """random_seeds: pick a fresh seed on every reset (the demo), rather
        than `game.seed` (agents and tests, for repeatable rounds).
        reward: the agent's reward profile, by name (rewards/<name>.json),
        path, or object. It never changes the game score.
        """
        self.config = config
        self.driver = driver  # shown in the HUD
        self.random_seeds = random_seeds
        self.reward_profile = (
            reward
            if isinstance(reward, RewardProfile)
            else load_reward_profile(reward)
        )
        self.renderer: Renderer | None = (
            Renderer(config) if config.show_gui else None
        )
        self.reset()

    def reset(self, seed: int | None = None) -> tuple[np.ndarray, dict]:
        """Starts a new game. Returns the first observation and info."""
        if seed is None and self.random_seeds:
            seed = random.SystemRandom().randrange(1_000_000)
        self.world, self.car = create_game(
            self.config, label=self.driver, seed=seed
        )
        self.running: bool = True
        return self.get_state(), self.info()

    def step(
        self, action: tuple
    ) -> tuple[np.ndarray, float, bool, bool, dict]:
        """One simulation step for an agent.

        action: 5 bools, in `action_names` order.
        Returns (observation, reward, terminated, truncated, info):
        terminated when the car is out (a crash), truncated when the round
        ran out of time. The reward comes from the reward profile, and is 0
        once the game is over. The game points gained are in info["points"].
        """
        score = self.world.component(self.car, CarScore)
        motion = self.world.component(self.car, Motion)
        checkpoints_before = score.checkpoints
        steering_before = motion.steering
        was_out, was_over = self._is_out(), self._round_over()

        points, _, _ = self.game_step(action)

        out = self._is_out()
        state = self.world.resource(RoundState)
        truncated = state.over and state.reason == "time" and not out
        observation = self.get_state()
        reward = 0.0
        if not was_over:
            sim = self.world.resource(SimConfig)
            events = StepEvents(
                points=points,
                checkpoints=score.checkpoints - checkpoints_before,
                crashed=out and not was_out,
                time_up=truncated,
                distance=max(motion.moved, 0.0),
                speed=motion.speed * sim.steps_per_second / sim.max_speed,
                steering_change=abs(motion.steering - steering_before),
                closest_wall=float(min(observation[:RAY_COUNT])),
            )
            reward = self.reward_profile(events)
        info = self.info()
        info["points"] = points
        return observation, reward, out, truncated, info

    def _is_out(self) -> bool:
        return self.world.try_component(self.car, Eliminated) is not None

    def _round_over(self) -> bool:
        return self.world.resource(RoundState).over

    def get_state(self) -> np.ndarray:
        """The observation: 14 floats, in `observation_names` order."""
        return observe(self.world, self.car)

    def info(self) -> dict:
        score = self.world.component(self.car, CarScore)
        eliminated = self.world.try_component(self.car, Eliminated)
        return {
            "score": score.total,
            "checkpoints": score.checkpoints,
            "step": self.world.resource(SimClock).step,
            "eliminated": eliminated.reason if eliminated else None,
        }

    @property
    def score(self) -> float:
        return self.world.component(self.car, CarScore).total

    @property
    def is_game_over(self) -> bool:
        return self.world.resource(RoundState).game_over

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
