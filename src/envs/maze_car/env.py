import random
from dataclasses import astuple
from typing import Optional

import numpy as np
from ml_collections import ConfigDict

from src.envs.base import Environment
from src.envs.maze_car.rewards import (
    RewardProfile,
    StepEvents,
    load_reward_profile,
)
from src.render.panels import RewardStatus
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
from src.sim.rules import Rules, load_rules
from src.sim.stage import Stage
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
        stage: Stage | None = None,
        rules: str | Rules | None = None,
        recorder=None,
    ) -> None:
        """random_seeds: pick a fresh seed on every reset (the demo), rather
        than `game.seed` (agents and tests, for repeatable rounds).
        reward: the agent's reward profile, by name (rewards/<name>.json),
        path, or object. It never changes the game score.
        stage: play this stage instead of loading `config.stage` (a replay
        passes its embedded stage).
        rules: game rules by name (rules/<name>.json), path, or object,
        instead of `config.rules`.
        recorder: records every game as a replay, through its on_reset,
        on_step, and on_finish hooks (src/replay/recorder.py).
        """
        self.config = config
        self.driver = driver  # shown in the HUD
        self.random_seeds = random_seeds
        self.stage = stage
        self.rules = load_rules(rules) if isinstance(rules, str) else rules
        self.recorder = recorder
        self.reward_profile = (
            reward
            if isinstance(reward, RewardProfile)
            else load_reward_profile(reward)
        )
        self.renderer: Renderer | None = (
            Renderer(config, stage) if config.show_gui else None
        )
        self.reset()

    def reset(self, seed: int | None = None) -> tuple[np.ndarray, dict]:
        """Starts a new game. Returns the first observation and info."""
        if seed is None and self.random_seeds:
            seed = random.SystemRandom().randrange(1_000_000)
        self.world, self.car = create_game(
            self.config,
            label=self.driver,
            seed=seed,
            stage=self.stage,
            rules=self.rules,
        )
        self.running: bool = True
        self.last_reward = 0.0
        self.round_reward = 0.0  # agent reward summed over this game
        self.last_observation = self.get_state()
        if self.recorder:
            self.recorder.on_reset(self)
        return self.last_observation, self.info()

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
        points, _, _ = self.game_step(action)
        info = self.info()
        info["points"] = points
        return (
            self.last_observation,
            self.last_reward,
            self._is_out(),
            self._time_up(),
            info,
        )

    def _is_out(self) -> bool:
        return self.world.try_component(self.car, Eliminated) is not None

    def _time_up(self) -> bool:
        state = self.world.resource(RoundState)
        return state.over and state.reason == "time" and not self._is_out()

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
        game is over. Also scores the step with the reward profile (for
        agents, and so the HUD can show it while a human drives).
        Returns the game points gained, game over, and the game score.
        """
        if self.is_game_over:
            self.last_reward = 0.0
            return (0, True, self.score)
        score = self.world.component(self.car, CarScore)
        motion = self.world.component(self.car, Motion)
        checkpoints_before = score.checkpoints
        distance_points_before = score.distance_points
        steering_before = motion.steering
        was_out = self._is_out()

        action_input = ActionInput(*action) if action else ActionInput()
        if self.recorder:
            step = self.world.resource(SimClock).step
            self.recorder.on_step(step, {"1": astuple(action_input)})
        self.world.add_component(self.car, action_input)
        self.world.step()

        points = score.last_step
        self.last_observation = self.get_state()
        sim = self.world.resource(SimConfig)
        events = StepEvents(
            points=points,
            checkpoints=score.checkpoints - checkpoints_before,
            crashed=self._is_out() and not was_out,
            time_up=self._time_up(),
            distance=max(motion.moved, 0.0),
            speed=motion.speed * sim.steps_per_second / sim.max_speed,
            steering_change=abs(motion.steering - steering_before),
            closest_wall=float(min(self.last_observation[:RAY_COUNT])),
            checkpoint_seconds=tuple(
                age / sim.steps_per_second for age in score.checkpoint_ages
            ),
            distance_points=score.distance_points - distance_points_before,
        )
        self.last_reward = self.reward_profile(events)
        self.round_reward += self.last_reward
        if self.recorder and self.is_game_over:
            self.recorder.on_finish(self)
        return (points, self.is_game_over, self.score)

    def finish_recording(self, reason: str = "stopped") -> None:
        """Ends the current recording early (for example when the player
        quits mid-game). Its replay then verifies up to this step.
        """
        if self.recorder and not self.recorder.finished:
            self.recorder.on_finish(self, reason)

    def reward_status(self) -> RewardStatus:
        return RewardStatus(
            profile=self.reward_profile.name,
            last=self.last_reward,
            total=self.round_reward,
        )

    def render(self, alpha: float = 1.0) -> float:
        """Handles window events and draws one frame. Returns the real
        seconds since the previous frame.
        """
        commands = self.renderer.poll_events()
        if Command.QUIT in commands:
            self.running = False
        if Command.RESTART in commands:
            self.reset()
        self.renderer.draw(self.world, alpha, self.reward_status())
        return self.renderer.present()
