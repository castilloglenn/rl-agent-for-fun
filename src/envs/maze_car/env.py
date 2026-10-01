import math
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
from src.sim.components import (
    ActionInput,
    Checkpoint,
    Eliminated,
    Health,
    Motion,
    Transform,
)
from src.sim.components import Score as CarScore
from src.sim.factories import create_game
from src.sim.observation import (
    OBSERVATION_NAMES,
    OBSERVATION_VERSION,
    observe,
)
from src.sim.paths import PathField
from src.sim.resources import Field, RoundState, SimClock, SimConfig, Walls
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
        if self.recorder and hasattr(self, "world"):
            self.recorder.on_before_reset(self)
        self.world, self.car = create_game(
            self.config,
            label=self.driver,
            seed=seed,
            stage=self.stage,
            rules=self.rules,
        )
        self.running: bool = True
        self._paths: dict[tuple, PathField] = {}  # by goal, this stage
        self.last_reward = 0.0
        self.round_reward = 0.0  # agent reward summed over this game
        # Each term's share of it, summed over this game (for the HUD).
        self.round_terms = {term: 0.0 for term in self.reward_profile.terms}
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
        terminated when the car is out (wrecked), truncated when the round
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

    # Progress along the path (7e)

    def _goal(self) -> tuple[float, float] | None:
        """The checkpoint the agent's compass points at: the nearest."""
        car = self.world.component(self.car, Transform)
        spots = [
            (spot.x, spot.y)
            for _, (spot, _) in self.world.query(Transform, Checkpoint)
        ]
        if not spots:
            return None
        return min(spots, key=lambda s: math.dist(s, (car.x, car.y)))

    def _path_distance(self, goal) -> float:
        """The car's path length to `goal` around the walls (inf: none)."""
        if goal is None:
            return math.inf
        path = self._paths.get(goal)
        if path is None:
            if len(self._paths) > 64:  # random checkpoints never repeat
                self._paths.clear()
            field = self.world.resource(Field)
            walls = self.world.resource(Walls).boxes
            path = PathField(
                (field.x, field.y, field.width, field.height),
                [(w.left, w.top, w.right, w.bottom) for w in walls],
                goal,
            )
            self._paths[goal] = path
        car = self.world.component(self.car, Transform)
        return path.distance(car.x, car.y)

    def _progress(self, goal, before: float, round_before: int) -> float:
        """px closer to the same checkpoint as before the step (reaching
        it spawns the next one, which isn't a step away). 0 across rounds
        or where there's no path.
        """
        if self.world.resource(RoundState).number != round_before:
            return 0.0
        after = self._path_distance(goal)
        if math.isinf(before) or math.isinf(after):
            return 0.0
        return before - after

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
            "health": self.world.component(self.car, Health).current,
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
        health = self.world.component(self.car, Health)
        health_before = health.current
        contacts_before = health.contacts
        touched_before = health.contact_step  # its last step at a wall
        was_out = self._is_out()
        # Progress along the path (7e), only for a profile that uses it.
        tracking = "progress" in self.reward_profile.terms
        goal = self._goal() if tracking else None
        round_before = self.world.resource(RoundState).number
        path_before = self._path_distance(goal)

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
            damage=(health_before - health.current) / health.maximum,
            wrecked=self._is_out() and not was_out,
            contacts=health.contacts - contacts_before,
            clear_seconds=_clear_seconds(
                touched_before, health.contact_step, sim.steps_per_second
            ),
            stopped=motion.speed == 0,
            time_up=self._time_up(),
            distance=max(motion.moved, 0.0),
            speed=motion.speed * sim.steps_per_second / sim.max_speed,
            steering_change=abs(motion.steering - steering_before),
            closest_wall=float(min(self.last_observation[:RAY_COUNT])),
            checkpoint_seconds=tuple(
                age / sim.steps_per_second for age in score.checkpoint_ages
            ),
            distance_points=score.distance_points - distance_points_before,
            progress=(
                self._progress(goal, path_before, round_before)
                if tracking
                else 0.0
            ),
            reversing=motion.speed < 0,
        )
        parts = self.reward_profile.contributions(events)
        self.last_reward = sum(parts.values())  # = reward_profile(events)
        self.round_reward += self.last_reward
        for term, value in parts.items():
            self.round_terms[term] += value
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
            terms=dict(self.round_terms),
            weights=dict(self.reward_profile.terms),
        )

    def render(self, alpha: float = 1.0, mode=None) -> float:
        """Handles window events and draws one frame. Returns the real
        seconds since the previous frame. mode: an optional ModeInfo (for
        example the recording indicator).
        """
        commands = self.renderer.poll_events(game_over=self.is_game_over)
        if Command.QUIT in commands:
            self.running = False
        if Command.RESTART in commands:
            self.reset()
        self.renderer.draw(self.world, alpha, self.reward_status(), mode)
        return self.renderer.present()


def _clear_seconds(before: int | None, now: int | None, sps: int) -> float:
    """Seconds between the car's last wall touch before this step and
    its touch this step (inf: no touch before). Only read for a new
    contact.
    """
    if before is None or now is None:
        return math.inf
    return max(now - before - 1, 0) / sps
