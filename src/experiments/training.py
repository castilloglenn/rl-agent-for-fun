"""Trains an agent with PPO, headless, into a run folder (roadmap 5a2).

    runs/<date>_<time>_train-<id>_seed<N>/
      config.json    agent, model, trainer, stage, rules, reward, ...
      metrics.csv    one row per training episode (same columns as runs)
      learning.csv   one row per update: losses, entropy, KL, ...
      replays/       every new best training episode, gzipped
      summary.json   totals, written at the end (also after Ctrl+C)
      notes.md       your observations

Weights go to the agent: agents/<id>/checkpoints/d0100k.pt, ...
"""

import csv
import json
import statistics
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import torch
from ml_collections import ConfigDict

from src.agents.ppo import Rollout, UpdateStats, update
from src.agents.store import LoadedAgent, load_agent, save_checkpoint
from src.agents.trainer import TrainerSpec
from src.config import game_config
from src.drivers.actions import CANONICAL_ACTIONS
from src.drivers.episode import EpisodeResult, episode_result
from src.envs.maze_car.env import MazeCarEnv
from src.envs.maze_car.rewards import RewardProfile
from src.experiments.runner import (
    METRICS_COLUMNS,
    RUN_FORMAT,
    RUNS_DIR,
    _metrics_row,
    _new_folder,
)
from src.replay.recorder import ReplayRecorder
from src.sim.rules import Rules
from src.sim.stage import Stage
from src.utils.version import code_version

LEARNING_COLUMNS = (
    "update",
    "decisions",
    "episodes",
    "seconds",
    "score_mean",  # game score, over the last RECENT episodes
    "reward_mean",  # agent reward, over the last RECENT episodes
    "policy_loss",
    "value_loss",
    "entropy",
    "approx_kl",
    "clip_fraction",
)
RECENT = 20  # episodes averaged in learning.csv and progress lines
SUMMARY_EPISODES = 100  # episodes behind the summary's mean and survival


@dataclass(frozen=True)
class UpdateReport:
    """Handed to `on_update` after every update, for progress lines."""

    update: int
    decisions: int  # this phase, so far
    total: int  # decisions this phase will run
    episodes: int
    score_mean: float | None  # last RECENT episodes
    stats: UpdateStats
    seconds: float
    saved: str | None  # checkpoint written after this update


@dataclass(frozen=True)
class TrainingSummary:
    folder: Path
    agent: str
    start_checkpoint: str
    decisions: int  # learned from in this phase
    agent_decisions: int  # over all phases, after this one
    updates: int
    episodes: int
    interrupted: bool
    mean_score: float  # last SUMMARY_EPISODES episodes
    best_score: float
    best_episode: int | None
    survival_rate: float  # last SUMMARY_EPISODES episodes
    checkpoints: tuple[str, ...]
    seconds: float


def checkpoint_name(decisions: int) -> str:
    """d0100k for 100,000 decisions, or the exact count if not round."""
    if decisions % 1000 == 0:
        return f"d{decisions // 1000:04d}k"
    return f"d{decisions:07d}"


def train_agent(
    agent: str | Path,
    trainer: TrainerSpec,
    config: ConfigDict,
    first_seed: int = 0,
    reward: str | RewardProfile = "default",
    rules: Rules | None = None,
    runs_dir: Path | None = None,
    agents_root: Path | None = None,
    on_update: Callable[[UpdateReport], None] | None = None,
) -> TrainingSummary:
    """One training phase: continues the agent's newest checkpoint for
    `trainer.total_decisions` decisions. Episode i uses seed first_seed + i.
    Ctrl+C stops it, keeping the metrics and the weights learned so far.
    """
    training = _Training(
        load_agent(agent, root=agents_root),
        trainer,
        config,
        first_seed,
        reward,
        rules,
        runs_dir or RUNS_DIR,
    )
    return training.run(on_update)


class _Training:
    def __init__(
        self,
        agent: LoadedAgent,
        trainer: TrainerSpec,
        config: ConfigDict,
        first_seed: int,
        reward: str | RewardProfile,
        rules: Rules | None,
        runs_dir: Path,
    ) -> None:
        self.agent = agent
        self.trainer = trainer
        self.first_seed = first_seed
        self.network = agent.network
        self.generator = torch.Generator().manual_seed(trainer.seed)
        self.optimizer = torch.optim.Adam(
            self.network.parameters(), lr=trainer.learning_rate, eps=1e-5
        )
        self.config = config.copy_and_resolve_references()
        self.config.show_gui = False
        self.recorder = ReplayRecorder({})
        self.env = MazeCarEnv(
            self.config,
            driver=f"{agent.agent_id} (training)",
            reward=reward,
            rules=rules,
            recorder=self.recorder,
        )
        self.name = f"train-{agent.agent_id}"
        self.folder = _new_folder(runs_dir, self.name, first_seed)
        self._write_config()
        (self.folder / "notes.md").write_text(
            f"# {self.name}\n\nYour observations.\n"
        )

        self.decisions = 0  # collected
        self.learned = 0  # collected and learned from (in the weights)
        self.updates = 0
        self.episode = 0
        self.results: list[EpisodeResult] = []
        self.recent: deque[EpisodeResult] = deque(maxlen=RECENT)
        self.best_score, self.best_episode = float("-inf"), None
        self.saved: list[str] = []
        self.saved_at = 0  # `learned` at the last checkpoint

    def run(self, on_update) -> TrainingSummary:
        started = time.perf_counter()
        interrupted = False
        folder = self.folder
        with (
            open(folder / "metrics.csv", "w", newline="") as metrics_file,
            open(folder / "learning.csv", "w", newline="") as learning_file,
        ):
            self.metrics_file = metrics_file
            self.metrics = csv.writer(metrics_file)
            self.metrics.writerow(METRICS_COLUMNS)
            learning = csv.writer(learning_file)
            learning.writerow(LEARNING_COLUMNS)
            try:
                self._start_episode()
                total = self.trainer.total_decisions
                while self.learned < total:
                    size = min(self.trainer.rollout, total - self.learned)
                    rollout = self._collect(size)
                    stats = update(
                        self.network,
                        self.optimizer,
                        rollout,
                        self.trainer,
                        self.generator,
                    )
                    self.updates += 1
                    self.learned = self.decisions
                    saved = self._maybe_save()
                    seconds = time.perf_counter() - started
                    learning.writerow(self._learning_row(stats, seconds))
                    learning_file.flush()
                    if on_update:
                        on_update(
                            UpdateReport(
                                self.updates,
                                self.learned,
                                total,
                                self.episode,
                                self._recent_mean("score"),
                                stats,
                                seconds,
                                saved,
                            )
                        )
            except KeyboardInterrupt:
                interrupted = True
                if self.learned > self.saved_at:
                    self._save(self.learned)
        return self._write_summary(interrupted, started)

    def _start_episode(self) -> None:
        # The replay's driver record says which training moment played it.
        self.recorder.drivers = {
            "1": {
                "type": "agent",
                "id": self.agent.agent_id,
                "checkpoint": None,
                "training": {
                    "run": self.folder.name,
                    "decisions": self.agent.decisions + self.decisions,
                },
            }
        }
        self.observation, _ = self.env.reset(
            seed=self.first_seed + self.episode
        )
        self.steps = 0

    def _collect(self, size: int) -> Rollout:
        """Plays `size` decisions with the current policy (sampled)."""
        buffer = {
            "observations": torch.zeros(size, len(self.observation)),
            "actions": torch.zeros(size, dtype=torch.long),
            "log_probs": torch.zeros(size),
            "values": torch.zeros(size),
            "rewards": torch.zeros(size),
            "dones": torch.zeros(size),
        }
        repeat = self.agent.spec.action_repeat
        for t in range(size):
            observation = torch.as_tensor(self.observation)
            with torch.no_grad():
                logits, value = self.network(observation.unsqueeze(0))
                log_probs = torch.log_softmax(logits[0], dim=-1)
                action = int(
                    torch.multinomial(
                        log_probs.exp(), 1, generator=self.generator
                    )
                )
            reward = 0.0
            done = truncated = False
            for _ in range(repeat):  # the decision is held `repeat` steps
                step = self.env.step(CANONICAL_ACTIONS[action])
                self.observation, step_reward, terminated, truncated = step[:4]
                info = step[4]
                self.steps += 1
                reward += step_reward
                done = terminated or truncated
                if done:
                    break
            buffer["observations"][t] = observation
            buffer["actions"][t] = action
            buffer["log_probs"][t] = log_probs[action]
            buffer["values"][t] = value[0]
            buffer["rewards"][t] = reward
            buffer["dones"][t] = float(done)
            self.decisions += 1
            if done:
                self._finish_episode(truncated, info)
        self.metrics_file.flush()

        with torch.no_grad():
            _, last_value = self.network(
                torch.as_tensor(self.observation).unsqueeze(0)
            )
        return Rollout(**buffer, last_value=float(last_value[0]))

    def _finish_episode(self, truncated: bool, info: dict) -> None:
        seed = self.first_seed + self.episode
        result = episode_result(self.env, seed, self.steps, truncated, info)
        self.results.append(result)
        self.recent.append(result)
        self.metrics.writerow(_metrics_row(self.episode, result, self.config))
        if result.score > self.best_score:
            self.best_score, self.best_episode = result.score, self.episode
            self.recorder.save(
                self.folder
                / "replays"
                / f"ep{self.episode:04d}_score{result.score:.0f}.jsonl.gz"
            )
        self.episode += 1
        self._start_episode()

    def _maybe_save(self) -> str | None:
        """Saves at each checkpoint_every mark, and at the end."""
        every = self.trainer.checkpoint_every
        if self.learned >= self.trainer.total_decisions:
            return self._save(self.learned)
        if self.learned // every > self.saved_at // every:
            return self._save(self.learned // every * every)
        return None

    def _save(self, mark: int) -> str:
        """Saves the weights, named by the phase mark they reached."""
        base = checkpoint_name(self.agent.decisions + mark)
        name, suffix = base, 1
        while (self.agent.folder / "checkpoints" / f"{name}.pt").exists():
            suffix += 1
            name = f"{base}_{suffix}"
        save_checkpoint(
            self.agent.folder,
            name,
            self.network,
            self.agent.spec,
            {
                "decisions": self.agent.decisions + self.learned,
                "run": self.folder.name,
                "trainer": self.trainer.name,
            },
        )
        self.saved.append(name)
        self.saved_at = self.learned
        return name

    def _recent_mean(self, key: str) -> float | None:
        if not self.recent:
            return None
        return statistics.mean(getattr(r, key) for r in self.recent)

    def _learning_row(self, stats: UpdateStats, seconds: float) -> list:
        score_mean = self._recent_mean("score")
        reward_mean = self._recent_mean("reward")
        return [
            self.updates,
            self.learned,
            self.episode,
            round(seconds, 3),
            "" if score_mean is None else round(score_mean, 3),
            "" if reward_mean is None else round(reward_mean, 3),
            *(round(value, 6) for value in asdict(stats).values()),
        ]

    def _write_config(self) -> None:
        world = self.env.world
        config = {
            "format": RUN_FORMAT,
            "kind": "training",
            "name": self.name,
            "created_at": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "code": code_version(),
            "driver": {"type": "agent", "id": self.agent.agent_id},
            "agent": {
                "id": self.agent.agent_id,
                "model": self.agent.spec.to_dict(),
                "start_checkpoint": self.agent.checkpoint,
                "start_decisions": self.agent.decisions,
            },
            "trainer": self.trainer.to_dict(),
            "first_seed": self.first_seed,
            "stage": world.resource(Stage).to_dict(),
            "rules": world.resource(Rules).to_dict(),
            "reward": self.env.reward_profile.to_dict(),
            "game_config": game_config(self.env.config),
            "observation_version": self.env.observation_version,
        }
        (self.folder / "config.json").write_text(
            json.dumps(config, indent=2) + "\n"
        )

    def _write_summary(self, interrupted: bool, started) -> TrainingSummary:
        last = self.results[-SUMMARY_EPISODES:]
        summary = TrainingSummary(
            folder=self.folder,
            agent=self.agent.agent_id,
            start_checkpoint=self.agent.checkpoint,
            decisions=self.learned,
            agent_decisions=self.agent.decisions + self.learned,
            updates=self.updates,
            episodes=len(self.results),
            interrupted=interrupted,
            mean_score=statistics.mean(r.score for r in last) if last else 0,
            best_score=self.best_score if last else 0,
            best_episode=self.best_episode,
            survival_rate=(
                sum(r.ended_by == "time" for r in last) / len(last)
                if last
                else 0
            ),
            checkpoints=tuple(self.saved),
            seconds=round(time.perf_counter() - started, 3),
        )
        (self.folder / "summary.json").write_text(
            json.dumps(
                {**asdict(summary), "folder": str(summary.folder)}, indent=2
            )
            + "\n"
        )
        return summary
