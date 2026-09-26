"""Runs a driver for many episodes, headless, into a run folder.

    runs/<date>_<time>_<name>_seed<N>/
      config.json    everything needed to reproduce the run
      metrics.csv    one row per episode, written as it goes
      replays/       every new best episode (by game score), gzipped
      summary.json   totals, written at the end (also after Ctrl+C)
      notes.md       your observations
"""

import csv
import json
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from ml_collections import ConfigDict

from src.config import game_config
from src.drivers.base import Driver
from src.drivers.episode import EpisodeResult, run_episode
from src.envs.maze_car.env import MazeCarEnv
from src.envs.maze_car.rewards import RewardProfile
from src.replay.recorder import ReplayRecorder
from src.sim.rules import Rules
from src.sim.stage import Stage
from src.utils.version import code_version

RUN_FORMAT = 1
RUNS_DIR = Path(__file__).resolve().parents[2] / "runs"
METRICS_COLUMNS = (
    "episode",
    "seed",
    "steps",
    "seconds",
    "score",
    "distance_points",
    "checkpoints",
    "reward",
    "ended_by",
)


@dataclass(frozen=True)
class RunSummary:
    folder: Path
    episodes: int
    interrupted: bool
    mean_score: float
    best_score: float
    best_episode: int | None
    mean_checkpoints: float
    survival_rate: float  # share of episodes that lasted the whole round
    seconds: float  # real time the run took


def run_experiment(
    name: str,
    driver: Driver,
    config: ConfigDict,
    episodes: int = 100,
    first_seed: int = 0,
    reward: str | RewardProfile = "default",
    rules: Rules | None = None,
    runs_dir: Path | None = None,
    on_episode: Callable[[int, EpisodeResult], None] | None = None,
) -> RunSummary:
    """Plays `episodes` games with `driver` (seeds first_seed, +1, ...)."""
    config = config.copy_and_resolve_references()
    config.show_gui = False
    recorder = ReplayRecorder({"1": driver.record()})
    env = MazeCarEnv(
        config,
        driver=driver.label,
        reward=reward,
        rules=rules,
        recorder=recorder,
    )
    folder = _new_folder(runs_dir or RUNS_DIR, name, first_seed)
    _write_config(folder, name, env, driver, episodes, first_seed)
    (folder / "notes.md").write_text(f"# {name}\n\nYour observations.\n")

    results: list[EpisodeResult] = []
    best_score, best_episode = float("-inf"), None
    started = time.perf_counter()
    interrupted = False
    with open(folder / "metrics.csv", "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(METRICS_COLUMNS)
        try:
            for episode in range(episodes):
                seed = first_seed + episode
                result = run_episode(env, driver, seed)
                results.append(result)
                writer.writerow(_metrics_row(episode, result, config))
                file.flush()
                if result.score > best_score:
                    best_score, best_episode = result.score, episode
                    recorder.save(
                        folder
                        / "replays"
                        / f"ep{episode:04d}_score{result.score:.0f}.jsonl.gz"
                    )
                if on_episode:
                    on_episode(episode, result)
        except KeyboardInterrupt:
            interrupted = True

    summary = _summarize(
        folder, results, interrupted, best_score, best_episode, started
    )
    (folder / "summary.json").write_text(
        json.dumps(
            {**asdict(summary), "folder": str(summary.folder)}, indent=2
        )
        + "\n"
    )
    return summary


def _new_folder(runs_dir: Path, name: str, first_seed: int) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    folder = runs_dir / f"{stamp}_{name}_seed{first_seed}"
    suffix = 1
    while folder.exists():  # two runs in the same second
        suffix += 1
        folder = runs_dir / f"{stamp}_{name}_seed{first_seed}_{suffix}"
    (folder / "replays").mkdir(parents=True)
    return folder


def _write_config(folder, name, env, driver, episodes, first_seed) -> None:
    world = env.world
    config = {
        "format": RUN_FORMAT,
        "name": name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "code": code_version(),
        "driver": driver.record(),
        "episodes": episodes,
        "first_seed": first_seed,
        "stage": world.resource(Stage).to_dict(),
        "rules": world.resource(Rules).to_dict(),
        "reward": env.reward_profile.to_dict(),
        "game_config": game_config(env.config),
        "observation_version": env.observation_version,
    }
    (folder / "config.json").write_text(json.dumps(config, indent=2) + "\n")


def _metrics_row(episode: int, result: EpisodeResult, config) -> list:
    seconds = result.steps / config.sim.steps_per_second
    return [
        episode,
        result.seed,
        result.steps,
        round(seconds, 3),
        result.score,
        result.distance_points,
        result.checkpoints,
        round(result.reward, 6),
        result.ended_by or "",
    ]


def _summarize(folder, results, interrupted, best, best_episode, started):
    count = len(results)
    return RunSummary(
        folder=folder,
        episodes=count,
        interrupted=interrupted,
        mean_score=statistics.mean(r.score for r in results) if count else 0,
        best_score=best if count else 0,
        best_episode=best_episode,
        mean_checkpoints=(
            statistics.mean(r.checkpoints for r in results) if count else 0
        ),
        survival_rate=(
            sum(r.ended_by == "time" for r in results) / count if count else 0
        ),
        seconds=round(time.perf_counter() - started, 3),
    )
