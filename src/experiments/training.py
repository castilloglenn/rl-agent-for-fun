"""Trains an agent with PPO, headless, into a run folder (roadmap 5a2),
and resumes a stopped one exactly (5a3).

    runs/<date>_<time>_train-<id>_seed<N>/
      config.json    agent, model, trainer, stage, rules, reward, ...
      metrics.csv    one row per training episode (same columns as runs)
      learning.csv   one row per update: losses, entropy, KL, ...
      replays/       every new best training episode, gzipped
      resume.pt      everything needed to continue exactly, after every
                     update: weights, optimizer, random state, counters,
                     and the current episode's actions so far
      summary.json   totals, written at the end (also after Ctrl+C)
      notes.md       your observations

Weights go to the agent: agents/<id>/checkpoints/d0100k.pt, ...
"""

import csv
import json
import os
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
from src.agents.store import (
    LoadedAgent,
    checkpoint_run,
    load_agent,
    save_checkpoint,
)
from src.agents.trainer import TrainerSpec
from src.config import config_with_game, game_config
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
RESUME_FORMAT = 1


class TrainingError(ValueError):
    pass


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
    resumes: int = 0  # times this run was resumed


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
    Ctrl+C stops it, keeping the metrics and the weights learned so far,
    and `resume_training` continues it exactly.
    """
    loaded = load_agent(agent, root=agents_root)
    config = config.copy_and_resolve_references()
    config.show_gui = False
    env = _env(loaded, config, reward, rules=rules)
    folder = _new_folder(
        runs_dir or RUNS_DIR, f"train-{loaded.agent_id}", first_seed
    )
    training = _Training(
        loaded,
        trainer,
        env,
        first_seed,
        folder,
        start_checkpoint=loaded.checkpoint,
        start_decisions=loaded.decisions,
        branched_from=loaded.branched_from,
    )
    training.write_config()
    (folder / "notes.md").write_text(
        f"# {folder.name}\n\nYour observations.\n"
    )
    return training.run(on_update)


def resume_training(
    run: str | Path,
    runs_dir: Path | None = None,
    agents_root: Path | None = None,
    base_config: ConfigDict | None = None,
    on_update: Callable[[UpdateReport], None] | None = None,
) -> TrainingSummary:
    """Continues a stopped training run exactly where its last update
    left it, with the run's own trainer, stage, rules, and reward. It ends
    as if it had never stopped.
    """
    folder = _run_folder(run, runs_dir)
    run_config = _read_json(folder / "config.json")
    if run_config.get("kind") != "training":
        raise TrainingError(f"{folder.name} is not a training run")
    summary = _read_json(folder / "summary.json")
    if summary and not summary.get("interrupted"):
        raise TrainingError(f"{folder.name} already finished")
    if not (folder / "resume.pt").exists():
        raise TrainingError(
            f"{folder.name} has no resume state (trained before 5a3?)"
        )
    _check_not_running(folder)
    state = torch.load(folder / "resume.pt", weights_only=True)
    if state.get("format") != RESUME_FORMAT:
        raise TrainingError(f"unsupported resume format in {folder.name}")

    agent_info = run_config["agent"]
    loaded = load_agent(agent_info["id"], root=agents_root)
    # Safety: if another run trained this agent since, continuing would
    # tangle its history.
    ours = loaded.run == folder.name
    if not ours and loaded.checkpoint != agent_info["start_checkpoint"]:
        raise TrainingError(
            f"agent {loaded.agent_id!r} has a newer checkpoint "
            f"({loaded.checkpoint}) from another run. Branch instead: "
            f"python app.py -new_agent <new_id> --from "
            f"{loaded.agent_id}@<checkpoint>"
        )

    config = config_with_game(run_config["game_config"], base_config)
    config.show_gui = False
    env = _env(
        loaded,
        config,
        RewardProfile.from_dict(run_config["reward"]),
        rules=Rules.from_dict(run_config["rules"]),
        stage=Stage.from_dict(run_config["stage"]),
    )
    training = _Training(
        loaded,
        TrainerSpec.from_dict(run_config["trainer"]),
        env,
        run_config["first_seed"],
        folder,
        start_checkpoint=agent_info["start_checkpoint"],
        start_decisions=agent_info["start_decisions"],
        branched_from=agent_info.get("branched_from"),
    )
    training.restore(state)
    return training.run(on_update)


def last_stopped_run(runs_dir: Path | None = None) -> Path:
    """The newest training run that stopped early and can be resumed."""
    for folder in sorted((runs_dir or RUNS_DIR).glob("*/"), reverse=True):
        config = _read_json(folder / "config.json")
        summary = _read_json(folder / "summary.json")
        if (
            config.get("kind") == "training"
            and summary.get("interrupted")
            and (folder / "resume.pt").exists()
        ):
            return folder
    raise TrainingError("no stopped training run to resume")


def _env(agent, config, reward, rules=None, stage=None) -> MazeCarEnv:
    return MazeCarEnv(
        config,
        driver=f"{agent.agent_id} (training)",
        reward=reward,
        rules=rules,
        stage=stage,
        recorder=ReplayRecorder({}),
    )


def _run_folder(run: str | Path, runs_dir: Path | None) -> Path:
    folder = Path(run)
    if not (folder / "config.json").exists():
        folder = (runs_dir or RUNS_DIR) / str(run)
    if not (folder / "config.json").exists():
        raise TrainingError(f"no run at {folder}")
    return folder


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _check_not_running(folder: Path) -> None:
    lock = folder / "training.lock"
    if not lock.exists():
        return
    try:
        os.kill(int(lock.read_text()), 0)
    except (ValueError, ProcessLookupError):
        return  # a leftover from a crash
    except PermissionError:
        pass  # alive, owned by someone else
    raise TrainingError(f"{folder.name} is still training")


class _Training:
    def __init__(
        self,
        agent: LoadedAgent,
        trainer: TrainerSpec,
        env: MazeCarEnv,
        first_seed: int,
        folder: Path,
        start_checkpoint: str,
        start_decisions: int,
        branched_from: dict | None,
    ) -> None:
        self.agent = agent
        self.trainer = trainer
        self.env = env
        self.recorder = env.recorder
        self.first_seed = first_seed
        self.folder = folder
        self.start_checkpoint = start_checkpoint
        self.start_decisions = start_decisions  # the agent's, at the start
        self.branched_from = branched_from
        self.network = agent.network
        self.generator = torch.Generator().manual_seed(trainer.seed)
        self.optimizer = torch.optim.Adam(
            self.network.parameters(), lr=trainer.learning_rate, eps=1e-5
        )

        self.decisions = 0  # collected
        self.learned = 0  # collected and learned from (in the weights)
        self.updates = 0
        self.episode = 0
        self.results: list[EpisodeResult] = []
        self.best_score, self.best_episode = float("-inf"), None
        self.saved: list[str] = []
        self.saved_at = 0  # `learned` at the last checkpoint
        self.seconds_before = 0.0  # training time before a resume
        self.resumes = 0
        self.resumed = False

    # Running

    def run(self, on_update) -> TrainingSummary:
        started = time.perf_counter()
        interrupted = False
        folder = self.folder
        lock = folder / "training.lock"
        lock.write_text(str(os.getpid()))
        mode = "a" if self.resumed else "w"
        try:
            with (
                open(folder / "metrics.csv", mode, newline="") as metrics_file,
                open(folder / "learning.csv", mode, newline="") as learn_file,
            ):
                self.metrics_file = metrics_file
                self.metrics = csv.writer(metrics_file)
                learning = csv.writer(learn_file)
                if not self.resumed:
                    self.metrics.writerow(METRICS_COLUMNS)
                    learning.writerow(LEARNING_COLUMNS)
                try:
                    self._train(learning, learn_file, started, on_update)
                except KeyboardInterrupt:
                    interrupted = True
            if interrupted:
                self._stop_at_last_update()
            return self._write_summary(interrupted, started)
        finally:
            lock.unlink(missing_ok=True)

    def _stop_at_last_update(self) -> None:
        """After Ctrl+C: back to the state right after the last update
        (Ctrl+C can land mid-update or mid-rollout), whose weights are
        kept as a checkpoint. Resuming continues from exactly there.
        """
        path = self.folder / "resume.pt"
        if not path.exists():  # stopped before the first update
            return
        state = torch.load(path, weights_only=True)
        self._restore_counters(state)
        _keep_rows(self.folder / "metrics.csv", self.episode)
        _keep_rows(self.folder / "learning.csv", self.updates)
        if self.learned > self.saved_at:
            self._save(self.learned)
            state["saved"], state["saved_at"] = list(self.saved), self.saved_at
            _write_atomic(state, path)

    def _train(self, learning, learn_file, started, on_update) -> None:
        if not self.resumed:
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
            seconds = self._seconds(started)
            learning.writerow(self._learning_row(stats, seconds))
            learn_file.flush()
            self._write_resume_state(started)
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

    def _seconds(self, started: float) -> float:
        return self.seconds_before + time.perf_counter() - started

    def _start_episode(self) -> None:
        # The replay's driver record says which training moment played it.
        self.episode_start = self.decisions
        self.episode_actions: list[int] = []
        self.recorder.drivers = {
            "1": {
                "type": "agent",
                "id": self.agent.agent_id,
                "checkpoint": None,
                "training": {
                    "run": self.folder.name,
                    "decisions": self.start_decisions + self.decisions,
                },
            }
        }
        self.observation, _ = self.env.reset(
            seed=self.first_seed + self.episode
        )
        self.steps = 0

    def _act(self, action: int) -> tuple[float, bool, bool, dict]:
        """Holds one decision for `action_repeat` steps, or until the
        episode ends. Returns (reward, done, truncated, info).
        """
        reward = 0.0
        done = truncated = False
        info: dict = {}
        self.episode_actions.append(action)
        for _ in range(self.agent.spec.action_repeat):
            step = self.env.step(CANONICAL_ACTIONS[action])
            self.observation, step_reward, terminated, truncated = step[:4]
            info = step[4]
            self.steps += 1
            reward += step_reward
            done = terminated or truncated
            if done:
                break
        return reward, done, truncated, info

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
            reward, done, truncated, info = self._act(action)
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
        self.metrics.writerow(
            _metrics_row(self.episode, result, self.env.config)
        )
        if result.score > self.best_score:
            self.best_score, self.best_episode = result.score, self.episode
            self.recorder.save(
                self.folder
                / "replays"
                / f"ep{self.episode:04d}_score{result.score:.0f}.jsonl.gz"
            )
        self.episode += 1
        self._start_episode()

    # Checkpoints and resume state

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
        base = checkpoint_name(self.start_decisions + mark)
        name, suffix = base, 1
        folder = self.agent.folder / "checkpoints"
        # A name this run already wrote is rewritten (a resume redoing an
        # update). Anyone else's is never overwritten.
        while (folder / f"{name}.pt").exists() and (
            checkpoint_run(folder / f"{name}.pt") != self.folder.name
        ):
            suffix += 1
            name = f"{base}_{suffix}"
        save_checkpoint(
            self.agent.folder,
            name,
            self.network,
            self.agent.spec,
            {
                "decisions": self.start_decisions + self.learned,
                "run": self.folder.name,
                "trainer": self.trainer.name,
            },
        )
        if name not in self.saved:
            self.saved.append(name)
        self.saved_at = self.learned
        return name

    def _write_resume_state(self, started: float) -> None:
        """Everything needed to continue from right after this update.
        The env is rebuilt by re-simulating the current episode's actions.
        """
        state = {
            "format": RESUME_FORMAT,
            "run": self.folder.name,
            "weights": self.network.state_dict(),
            "optimizer": self.optimizer.state_dict(),
            "generator": self.generator.get_state(),
            "learned": self.learned,
            "updates": self.updates,
            "episode": self.episode,
            "results": [asdict(result) for result in self.results],
            "best_score": self.best_score,
            "best_episode": self.best_episode,
            "saved": list(self.saved),
            "saved_at": self.saved_at,
            "seconds": self._seconds(started),
            "resumes": self.resumes,
            "episode_start": self.episode_start,
            "episode_actions": list(self.episode_actions),
        }
        _write_atomic(state, self.folder / "resume.pt")

    def restore(self, state: dict) -> None:
        if state["run"] != self.folder.name:
            raise TrainingError("resume state belongs to another run")
        self._restore_counters(state)
        self.seconds_before = state["seconds"]
        self.resumes = state["resumes"] + 1
        self.resumed = True

        # Rows written after that update are replayed again: drop them.
        _keep_rows(self.folder / "metrics.csv", self.episode)
        _keep_rows(self.folder / "learning.csv", self.updates)

        # Rebuild the current episode by playing its actions again.
        self.decisions = state["episode_start"]
        self._start_episode()
        for action in state["episode_actions"]:
            self._act(action)
        self.decisions = self.learned

    def _restore_counters(self, state: dict) -> None:
        """The learner and counters as they were right after an update."""
        self.network.load_state_dict(state["weights"])
        self.optimizer.load_state_dict(state["optimizer"])
        self.generator.set_state(state["generator"])
        self.decisions = self.learned = state["learned"]
        self.updates = state["updates"]
        self.episode = state["episode"]
        self.results = [EpisodeResult(**row) for row in state["results"]]
        self.best_score = state["best_score"]
        self.best_episode = state["best_episode"]
        self.saved = list(state["saved"])
        self.saved_at = state["saved_at"]

    # Files

    def _recent_mean(self, key: str) -> float | None:
        recent = self.results[-RECENT:]
        if not recent:
            return None
        return statistics.mean(getattr(r, key) for r in recent)

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

    def write_config(self) -> None:
        world = self.env.world
        config = {
            "format": RUN_FORMAT,
            "kind": "training",
            "name": self.folder.name,
            "created_at": datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
            "code": code_version(),
            "driver": {"type": "agent", "id": self.agent.agent_id},
            "agent": {
                "id": self.agent.agent_id,
                "model": self.agent.spec.to_dict(),
                "start_checkpoint": self.start_checkpoint,
                "start_decisions": self.start_decisions,
                "branched_from": self.branched_from,
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
            start_checkpoint=self.start_checkpoint,
            decisions=self.learned,
            agent_decisions=self.start_decisions + self.learned,
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
            seconds=round(self._seconds(started), 3),
            resumes=self.resumes,
        )
        (self.folder / "summary.json").write_text(
            json.dumps(
                {**asdict(summary), "folder": str(summary.folder)}, indent=2
            )
            + "\n"
        )
        return summary


def _write_atomic(state: dict, path: Path) -> None:
    """Writes a torch file so that a crash never leaves it half-written."""
    temporary = path.with_name(path.name + ".tmp")
    torch.save(state, temporary)
    os.replace(temporary, path)


def _keep_rows(path: Path, rows: int) -> None:
    """Keeps a CSV's header and its first `rows` rows."""
    with open(path, newline="") as file:
        lines = list(csv.reader(file))
    with open(path, "w", newline="") as file:
        csv.writer(file).writerows(lines[: rows + 1])
