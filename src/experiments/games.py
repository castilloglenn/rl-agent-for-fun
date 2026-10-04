"""Training's games (roadmap 8, decision 073): one training plays several
games at once, each in its own process, and one network decides for all.

A `Game` is one MazeCarEnv with its replay recorder: it starts rounds,
holds each decision for the model's `action_repeat` steps, and saves a
finished round's replay when asked. The training process talks to each
game through a handle with the same two calls, `send` then `receive`:

- `LocalGame`: the game in the training process itself (one game: no
  worker, and the run is the same as before step 8);
- `WorkerGame`: the game in a worker process (`python -m
  src.experiments.game_worker`), started as a plain subprocess, so it
  never imports app.py or torch. It ends when the training process does:
  its pipe closes.

Messages are tuples, answered in order:
    ("start", seed, stage, drivers, save_as) -> observation
        saves the finished round's replay first, if save_as is a path
    ("act", action) -> Step
    ("close", save_as) -> None
No torch here: a worker stays small.
"""

import os
import pickle
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from ml_collections import ConfigDict

from src.drivers.actions import CANONICAL_ACTIONS
from src.drivers.episode import EpisodeResult, episode_result
from src.envs.maze_car.env import MazeCarEnv
from src.envs.maze_car.rewards import RewardProfile
from src.replay.recorder import ReplayRecorder
from src.sim.rules import Rules
from src.sim.stage import Stage

REPO = Path(__file__).resolve().parents[2]


class GameError(RuntimeError):
    """A game failed (its worker's error, or the worker is gone)."""


@dataclass(frozen=True)
class GameSetup:
    """Everything a game needs, as plain data (it crosses to a worker)."""

    config: ConfigDict
    driver: str  # shown in the HUD of its replays
    reward: dict  # RewardProfile.to_dict()
    rules: dict  # Rules.to_dict()
    stages: tuple[dict, ...]  # Stage.to_dict(): the maps it can play
    action_repeat: int


@dataclass(frozen=True)
class Step:
    """One decision, held: what the game answers to "act"."""

    observation: object  # the env's own array
    reward: float
    done: bool
    result: EpisodeResult | None  # the round's, when it ended
    stage: str  # the map this round plays


class Game:
    """One game: an env and its recorder (in a worker, or in-process)."""

    def __init__(self, setup: GameSetup) -> None:
        self.setup = setup
        self.stages = {
            data["name"]: Stage.from_dict(data) for data in setup.stages
        }
        self.recorder = ReplayRecorder({})
        self.env = MazeCarEnv(
            setup.config,
            driver=setup.driver,
            reward=RewardProfile.from_dict(setup.reward),
            rules=Rules.from_dict(setup.rules),
            stage=next(iter(self.stages.values())),
            recorder=self.recorder,
        )
        self.seed: int | None = None
        self.steps = 0

    def handle(self, message: tuple):
        kind = message[0]
        if kind == "start":
            return self.start(*message[1:])
        if kind == "act":
            return self.act(message[1])
        if kind == "close":
            self._save(message[1])
            return None
        raise GameError(f"unknown message {kind!r}")

    def start(self, seed: int, stage: str, drivers: dict, save_as):
        self._save(save_as)
        self.recorder.drivers = drivers
        self.env.stage = self.stages[stage]
        observation, _ = self.env.reset(seed=seed)
        self.seed, self.steps = seed, 0
        return observation

    def act(self, action: int) -> Step:
        """Holds one decision for `action_repeat` steps, or until the
        round ends.
        """
        reward = 0.0
        done = truncated = False
        info: dict = {}
        for _ in range(self.setup.action_repeat):
            observation, step_reward, terminated, truncated, info = (
                self.env.step(CANONICAL_ACTIONS[action])
            )
            self.steps += 1
            reward += step_reward
            done = terminated or truncated
            if done:
                break
        result = None
        if done:
            result = episode_result(
                self.env, self.seed, self.steps, truncated, info
            )
        return Step(
            observation, reward, done, result, self.env.stage.name
        )

    def _save(self, save_as) -> None:
        if save_as is not None:
            self.recorder.save(save_as)


class LocalGame:
    """A game in this process: no worker (one game)."""

    def __init__(self, setup: GameSetup) -> None:
        self.game = Game(setup)
        self._answer = None

    def send(self, message: tuple) -> None:
        self._answer = self.game.handle(message)

    def receive(self):
        answer, self._answer = self._answer, None
        return answer

    def close(self, save_as=None) -> None:
        self.game.handle(("close", save_as))


class WorkerGame:
    """A game in a worker process. Its pipe is its lifeline: when the
    training process ends (even killed), the pipe closes and the worker
    ends too. It inherits the training's low priority.
    """

    def __init__(self, setup: GameSetup) -> None:
        environment = {**os.environ, "PYGAME_HIDE_SUPPORT_PROMPT": "1"}
        self.process = subprocess.Popen(
            [sys.executable, "-m", "src.experiments.game_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            cwd=REPO,
            env=environment,
        )
        self.send(("setup", setup))
        self.receive()

    def send(self, message: tuple) -> None:
        try:
            pickle.dump(message, self.process.stdin, pickle.HIGHEST_PROTOCOL)
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            raise GameError(f"a game's worker is gone ({error})") from error

    def receive(self):
        try:
            kind, answer = pickle.load(self.process.stdout)
        except (EOFError, pickle.UnpicklingError) as error:
            raise GameError(
                f"a game's worker ended (exit {self.process.poll()})"
            ) from error
        if kind == "error":
            raise GameError(f"a game's worker failed:\n{answer}")
        return answer

    def close(self, save_as=None) -> None:
        """Saves the finished round if asked, then ends the worker."""
        try:
            self.send(("close", save_as))
            self.receive()
        except GameError:
            pass  # already gone: nothing to save
        for stream in (self.process.stdin, self.process.stdout):
            try:
                stream.close()
            except OSError:
                pass
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()


def open_game(setup: GameSetup, worker: bool):
    """A game handle: in a worker process, or in this one."""
    return WorkerGame(setup) if worker else LocalGame(setup)
