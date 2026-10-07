"""Trains an agent with PPO, headless, into a run folder (roadmap 5a2),
and resumes a stopped one exactly (5a3).

    runs/<date>_<time>_train-<id>_seed<N>/
      config.json    agent, model, trainer, stage, rules, reward, ...
      metrics.csv    one row per training episode (same columns as runs)
      learning.csv   one row per update: losses, entropy, KL, ...
      replays/       every new best training episode, gzipped
      resume.pt      everything needed to continue after every update:
                     weights, optimizer, random state, counters (a resume
                     starts fresh rounds, and is exact from there)
      summary.json   totals, written at the end (also after Ctrl+C)
      notes.md       your observations

Weights go to the agent: agents/<id>/checkpoints/d0100k.pt, ...

Several games at once (roadmap 8, decision 073): one network decides for
all of them in one pass, each game in its own worker process
(`games.py`), as many as the machine has room for (`game_count.py`). The
rollout stays `trainer.rollout` decisions in total, split over the games,
and each update learns from every game's piece.
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

import numpy as np
import torch
from ml_collections import ConfigDict

from src.agents.history import record
from src.agents.ppo import Rollout, UpdateStats, update
from src.agents.store import (
    LoadedAgent,
    checkpoint_run,
    load_agent,
    save_checkpoint,
)
from src.agents.trainer import TrainerSpec
from src.config import config_with_game, game_config
from src.drivers.episode import EpisodeResult
from src.envs.maze_car.env import MazeCarEnv
from src.envs.maze_car.rewards import RewardProfile
from src.experiments.evaluation import (
    DEFAULT_SUITE,
    evaluate_checkpoint,
    load_suite,
)
from src.experiments.game_count import FixedCount, GameCount
from src.experiments.games import GameSetup, Step, open_game
from src.experiments.runner import (
    RUN_FORMAT,
    RUNS_DIR,
    _metrics_row,
    _new_folder,
    metrics_columns,
)
from src.replay.recorder import ReplayRecorder
from src.sim.rules import Rules
from src.sim.stage import Stage, load_stage
from src.utils.curricula import (
    Curriculum,
    CurriculumState,
    Teacher,
    is_curriculum,
    load_curriculum,
)
from src.utils.mixes import Mix, is_mix, load_mix
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
    "anchor_kl",  # how far from the anchor, with `trainer.anchor` (0: off)
    "level",  # the curriculum's level (7f5), 1 up; blank without one
    "games",  # games that played this rollout (step 8)
)
RECENT = 20  # episodes averaged in learning.csv and progress lines
EPISODE_SUMMARY = 100  # a history summary line per this many episodes
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
    evaluation: dict | None = None  # its suite scores, if evaluated
    games: int = 1  # games that played this rollout


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
    suite: str = DEFAULT_SUITE,
    on_start: Callable[[Path], None] | None = None,
    games: int = 1,
    adapt: bool = False,
    count: GameCount | FixedCount | None = None,
    workers: bool | None = None,
) -> TrainingSummary:
    """One training phase: continues the agent's newest checkpoint for
    `trainer.total_decisions` decisions. The i-th round to start uses
    seed first_seed + i. Ctrl+C stops it, keeping the metrics and the
    weights learned so far, and `resume_training` continues it.

    games: the most at once. adapt: follow the machine's free room
    (`GameCount`); without it, always `games` (the same seed and games:
    the same run). workers: games in worker processes (default: with
    more than one).
    """
    loaded = load_agent(agent, root=agents_root)
    config = config.copy_and_resolve_references()
    config.show_gui = False
    # A mix plays its maps in turn (7d5a); a curriculum plays its levels'
    # maps by share and moves up by itself (7f5); a stage plays as before.
    curriculum = (
        load_curriculum(config.stage) if is_curriculum(config.stage) else None
    )
    if curriculum:
        mix = Mix(curriculum.name, tuple(curriculum.all_maps()))
    else:
        mix = load_mix(config.stage) if is_mix(config.stage) else None
    stages = [load_stage(name) for name in mix.stages] if mix else []
    first = stages[0] if stages else None
    env = _env(loaded, config, reward, rules=rules, stage=first)
    teacher = None
    if curriculum:
        from src.experiments.map_baselines import heuristic_rates

        rates = heuristic_rates(
            list(mix.stages),
            env.world.resource(Rules),
            agents_root or loaded.folder.parent,
            config,
        )
        start = _curriculum_level(loaded.folder, curriculum)
        teacher = Teacher(
            curriculum,
            curriculum.level_maps(),
            rates,
            CurriculumState(level=start),
        )
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
        suite=suite,
        mix=mix,
        stages=stages,
        teacher=teacher,
        count=count or _count(games, adapt),
        workers=games > 1 if workers is None else workers,
    )
    training.write_config()
    if on_start:
        on_start(folder)
    world = env.world
    record(
        loaded.folder,
        "phase_started",
        run=folder.name,
        trainer=trainer.name,
        reward=env.reward_profile.name,
        stage=world.resource(Stage).name,
        rules=world.resource(Rules).name,
        start_checkpoint=loaded.checkpoint,
        start_decisions=loaded.decisions,
        **({"mix": mix.name, "stages": list(mix.stages)} if mix else {}),
        **({"curriculum": curriculum.name} if curriculum else {}),
    )
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
    suite: str = DEFAULT_SUITE,
    on_start: Callable[[Path], None] | None = None,
    adapt: bool = False,
    count: GameCount | FixedCount | None = None,
) -> TrainingSummary:
    """Continues a stopped training run from its last update, with the
    run's own trainer, stage, rules, reward, and most games. Rounds start
    fresh (the ones playing when it stopped are dropped); from there it's
    exact: resuming the same state twice gives the same run.
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
    mixed = run_config.get("mix")  # the maps as they were (7d5a)
    stages = [Stage.from_dict(s) for s in mixed["stages"]] if mixed else []
    mix = Mix(mixed["name"], tuple(s.name for s in stages)) if mixed else None
    taught = run_config.get("curriculum")  # as it was (7f5)
    teacher = None
    if taught:
        teacher = Teacher(
            Curriculum.from_dict(taught["spec"]),
            taught["level_maps"],
            taught["heuristic"],
        )
    env = _env(
        loaded,
        config,
        RewardProfile.from_dict(run_config["reward"]),
        rules=Rules.from_dict(run_config["rules"]),
        stage=stages[0] if stages else Stage.from_dict(run_config["stage"]),
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
        suite=(run_config.get("suite") or {}).get("name", suite),
        mix=mix,
        stages=stages,
        teacher=teacher,
        count=count or _count(run_config["games"], adapt),
        workers=run_config["games"] > 1,
    )
    training.restore(state)
    if on_start:
        on_start(folder)
    record(
        loaded.folder,
        "phase_resumed",
        run=folder.name,
        decisions=training.start_decisions + training.learned,
    )
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


def _curriculum_level(folder: Path, curriculum: Curriculum) -> int:
    """Where this agent left the curriculum (0-based): a new phase picks
    up at its last level, not at the start.
    """
    from src.agents.history import read_history

    level = 0
    for event in read_history(folder):
        if (
            event.get("event") == "level_up"
            and event.get("curriculum") == curriculum.name
        ):
            level = event["level"] - 1
    return min(level, len(curriculum.levels) - 1)


def _count(games: int, adapt: bool) -> GameCount | FixedCount:
    return GameCount(games) if adapt and games > 1 else FixedCount(games)


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


@dataclass(eq=False)
class _Slot:
    """A game the training plays, and the round it plays now."""

    number: int  # 1 up, in the order the games were opened
    game: object  # a LocalGame or a WorkerGame
    observation: object = None
    round: int = 0  # its seed is first_seed + round
    stage: str = ""
    leaving: bool = False  # stops when this round ends
    save_as: Path | None = None  # its finished round's replay, a new best


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
        suite: str = DEFAULT_SUITE,
        mix: Mix | None = None,
        stages: list[Stage] | None = None,
        teacher: Teacher | None = None,
        count: GameCount | FixedCount | None = None,
        workers: bool = False,
    ) -> None:
        self.agent = agent
        # A mix's maps, each round on the one furthest behind (7d5a, step
        # 8); with a curriculum, its teacher picks each round's map (7f5).
        self.mix = mix
        self.stages = stages or []
        self.teacher = teacher
        # Scoring checkpoints plays separate games with its own driver, so
        # it never changes the training.
        self.suite = load_suite(suite) if trainer.evaluate else None
        self.trainer = trainer
        # The run's settings (config, reward, rules, stage); the games
        # play elsewhere, each with its own env.
        self.env = env
        self.config = env.config
        self.terms = tuple(env.reward_profile.terms)
        world = env.world
        played = self.stages or [world.resource(Stage)]
        self.setup = GameSetup(
            env.config,
            env.driver,
            env.reward_profile.to_dict(),
            world.resource(Rules).to_dict(),
            tuple(stage.to_dict() for stage in played),
            agent.spec.action_repeat,
        )
        self.count = count or FixedCount(1)
        self.workers = workers
        self.slots: list[_Slot] = []
        self.opened = 0  # games opened so far (their numbers)
        self.first_seed = first_seed
        self.folder = folder
        self.start_checkpoint = start_checkpoint
        self.start_decisions = start_decisions  # the agent's, at the start
        self.branched_from = branched_from
        self.network = agent.network
        # With `trainer.anchor`: the phase's starting weights, fixed, to
        # stay close to (a branch's "initial" is its source checkpoint).
        self.anchor = None
        if trainer.anchor > 0:
            self.anchor = load_agent(agent.folder, start_checkpoint).network
            self.anchor.eval()
        self.generator = torch.Generator().manual_seed(trainer.seed)
        self.optimizer = torch.optim.Adam(
            self.network.parameters(), lr=trainer.learning_rate, eps=1e-5
        )

        self.decisions = 0  # collected
        self.learned = 0  # collected and learned from (in the weights)
        self.updates = 0
        self.episode = 0  # rounds finished (metrics rows)
        self.rounds = 0  # rounds started (their seeds)
        self.map_counts: dict[str, int] = {}  # a mix's rounds per map
        self.games = 0  # games that played the last rollout
        self.results: list[EpisodeResult] = []
        self.best_score, self.best_episode = float("-inf"), None
        # The best score on each map so far: a replay is saved for a new
        # best on its map (a mix's maps each keep theirs, 7d5).
        self.best_by_map: dict[str, float] = {}
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
                    self.metrics.writerow(metrics_columns(self.terms))
                    learning.writerow(LEARNING_COLUMNS)
                try:
                    self._train(learning, learn_file, started, on_update)
                except KeyboardInterrupt:
                    interrupted = True
                finally:
                    self._close_games()
            if interrupted:
                self._stop_at_last_update()
            return self._write_summary(interrupted, started)
        finally:
            lock.unlink(missing_ok=True)

    def _stop_at_last_update(self) -> None:
        """After Ctrl+C: back to the state right after the last update
        (Ctrl+C can land mid-update or mid-rollout), whose weights are
        kept as a checkpoint. Resuming continues from there.
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
        first = self.count.first()
        for _ in range(first):
            self._open_game()
        if self.count.most > 1:
            print(f"Games: {first} at once, up to {self.count.most}", flush=True)
        total = self.trainer.total_decisions
        while self.learned < total:
            size = min(self.trainer.rollout, total - self.learned)
            rollouts = self._collect(size)
            stats = update(
                self.network,
                self.optimizer,
                rollouts,
                self.trainer,
                self.generator,
                self.anchor,
            )
            self.updates += 1
            self.learned = self.decisions
            saved = self._maybe_save()
            evaluation = None
            if saved and self.suite:
                evaluation = evaluate_checkpoint(
                    self.agent.folder, saved, self.suite, self.config
                )
            seconds = self._seconds(started)
            learning.writerow(self._learning_row(stats, seconds))
            learn_file.flush()
            self._write_resume_state(started)
            if self.learned < total:
                self._adjust_games()
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
                        evaluation,
                        self.games,
                    )
                )

    def _seconds(self, started: float) -> float:
        return self.seconds_before + time.perf_counter() - started

    # Games and rounds

    def _open_game(self) -> None:
        self.opened += 1
        slot = _Slot(self.opened, open_game(self.setup, self.workers))
        self.slots.append(slot)
        self._start_round(slot)

    def _close_games(self) -> None:
        """Ends every game (the end of training, or Ctrl+C): rounds still
        playing are dropped.
        """
        for slot in self.slots:
            try:
                slot.game.close()
            except Exception:  # noqa: BLE001 - closing never hides the why
                pass
        self.slots = []

    def _adjust_games(self) -> None:
        """One game more or fewer, if the machine says so (after an
        update). A game leaving finishes its round first.
        """
        staying = [slot for slot in self.slots if not slot.leaving]
        change = self.count.check(len(staying))
        if change is None:
            return
        games, why = change
        if games < len(staying):
            staying[-1].leaving = True  # the newest goes first
        else:
            self._open_game()
        print(f"Games: {games} ({why})", flush=True)

    def _start_round(self, slot: _Slot) -> None:
        """Starts the slot's next round (saving its last one first, if it
        was a new best). The replay's driver record says which training
        moment played it.
        """
        slot.round, self.rounds = self.rounds, self.rounds + 1
        slot.stage = self._next_map()
        drivers = {
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
        slot.game.send(
            (
                "start",
                self.first_seed + slot.round,
                slot.stage,
                drivers,
                slot.save_as,
            )
        )
        slot.observation = slot.game.receive()
        slot.save_as = None

    def _next_map(self) -> str:
        """This round's map: the curriculum's pick, a mix's map furthest
        behind (one game: in turn), or the one stage.
        """
        if not self.stages:
            return self.setup.stages[0]["name"]
        if self.teacher:
            name = self.teacher.next_map()
            self.teacher.started(name)
            return name
        name = min(
            (stage.name for stage in self.stages),
            key=lambda n: self.map_counts.get(n, 0),
        )
        self.map_counts[name] = self.map_counts.get(name, 0) + 1
        return name

    def _collect(self, size: int) -> list[Rollout]:
        """Plays `size` decisions with the current policy (sampled), split
        over the games: one rollout per game. The games step together, and
        one network pass decides for all of them.
        """
        slots = list(self.slots)
        self.games = len(slots)
        quota = {
            slot.number: size // len(slots) + (i < size % len(slots))
            for i, slot in enumerate(slots)
        }
        names = (
            "observations", "actions", "log_probs", "values", "rewards",
            "dones",
        )
        buffers = {slot.number: {name: [] for name in names} for slot in slots}
        while True:
            acting = [
                slot
                for slot in slots
                if slot in self.slots
                and len(buffers[slot.number]["actions"]) < quota[slot.number]
            ]
            if not acting:
                break
            observations = torch.as_tensor(
                np.stack([slot.observation for slot in acting])
            )
            with torch.no_grad():
                logits, values = self.network(observations)
                log_probs = torch.log_softmax(logits, dim=-1)
                actions = [
                    int(
                        torch.multinomial(
                            log_probs[i].exp(), 1, generator=self.generator
                        )
                    )
                    for i in range(len(acting))
                ]
            for slot, action in zip(acting, actions):
                slot.game.send(("act", action))
            for i, slot in enumerate(acting):
                step: Step = slot.game.receive()
                buffer = buffers[slot.number]
                buffer["observations"].append(observations[i])
                buffer["actions"].append(actions[i])
                buffer["log_probs"].append(log_probs[i, actions[i]])
                buffer["values"].append(values[i])
                buffer["rewards"].append(
                    step.reward * self.trainer.reward_scale
                )
                buffer["dones"].append(float(step.done))
                self.decisions += 1
                slot.observation = step.observation
                if step.done:
                    self._finish_round(slot, step)
        self.metrics_file.flush()

        rollouts = []
        for slot in slots:
            buffer = buffers[slot.number]
            if not buffer["actions"]:
                continue
            last_value = 0.0  # a game that left ended its round: unused
            if slot in self.slots:
                with torch.no_grad():
                    _, value = self.network(
                        torch.as_tensor(slot.observation).unsqueeze(0)
                    )
                last_value = float(value[0])
            rollouts.append(
                Rollout(
                    observations=torch.stack(buffer["observations"]),
                    actions=torch.tensor(buffer["actions"], dtype=torch.long),
                    log_probs=torch.stack(buffer["log_probs"]),
                    values=torch.stack(buffer["values"]),
                    rewards=torch.tensor(
                        buffer["rewards"], dtype=torch.float32
                    ),
                    dones=torch.tensor(buffer["dones"], dtype=torch.float32),
                    last_value=last_value,
                )
            )
        return rollouts

    def _finish_round(self, slot: _Slot, step: Step) -> None:
        result = step.result
        self.results.append(result)
        self.metrics.writerow(
            _metrics_row(
                self.episode,
                result,
                self.config,
                step.stage,
                self.terms,
                game=slot.number,
            )
        )
        if result.score > self.best_score:
            self.best_score, self.best_episode = result.score, self.episode
        stage = step.stage
        if self.teacher:
            sps = self.config.sim.steps_per_second
            self.teacher.played(
                stage, result.fuels, result.steps / sps / 60
            )
            self._check_level()
        if result.score > self.best_by_map.get(stage, float("-inf")):
            self.best_by_map[stage] = result.score
            slot.save_as = (
                self.folder
                / "replays"
                / f"ep{self.episode:04d}_score{result.score:.0f}.jsonl.gz"
            )
        if (self.episode + 1) % EPISODE_SUMMARY == 0:
            last = self.results[-EPISODE_SUMMARY:]
            record(
                self.agent.folder,
                "episodes",
                run=self.folder.name,
                first=self.episode - EPISODE_SUMMARY + 1,
                last=self.episode,
                score_mean=round(statistics.mean(r.score for r in last), 1),
                score_min=min(r.score for r in last),
                score_max=max(r.score for r in last),
                wreck_rate=sum(r.ended_by == "wrecked" for r in last)
                / len(last),
            )
        self.episode += 1
        if slot.leaving:
            slot.game.close(slot.save_as)
            self.slots.remove(slot)
        else:
            self._start_round(slot)

    def _check_level(self) -> None:
        """Moves up the curriculum when it's time (7f5), and says so."""
        why = self.teacher.check(self.learned)
        if why is None:
            return
        level = self.teacher.state.level + 1
        record(
            self.agent.folder,
            "level_up",
            run=self.folder.name,
            curriculum=self.teacher.curriculum.name,
            level=level,
            why=why,
            decisions=self.start_decisions + self.learned,
        )
        print(
            f"Curriculum {self.teacher.curriculum.name}: level {level} "
            f"({'goal reached' if why == 'goal' else 'its time ran out'})",
            flush=True,
        )

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
        record(
            self.agent.folder,
            "checkpoint_saved",
            run=self.folder.name,
            checkpoint=name,
            decisions=self.start_decisions + self.learned,
        )
        self.saved_at = self.learned
        return name

    def _write_resume_state(self, started: float) -> None:
        """Everything needed to continue from right after this update.
        The rounds playing then aren't kept: a resume starts fresh ones.
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
            "rounds": self.rounds,
            "map_counts": dict(self.map_counts),
            "results": [asdict(result) for result in self.results],
            "best_score": self.best_score,
            "best_episode": self.best_episode,
            "best_by_map": dict(self.best_by_map),
            "saved": list(self.saved),
            "saved_at": self.saved_at,
            "seconds": self._seconds(started),
            "resumes": self.resumes,
            "curriculum": (
                self.teacher.state.to_dict() if self.teacher else None
            ),
        }
        _write_atomic(state, self.folder / "resume.pt")

    def restore(self, state: dict) -> None:
        if state["run"] != self.folder.name:
            raise TrainingError("resume state belongs to another run")
        self._restore_counters(state)
        self.seconds_before = state["seconds"]
        self.resumes = state["resumes"] + 1
        self.resumed = True

        # Rows written after that update are played again: drop them.
        _keep_rows(self.folder / "metrics.csv", self.episode)
        _keep_rows(self.folder / "learning.csv", self.updates)

    def _restore_counters(self, state: dict) -> None:
        """The learner and counters as they were right after an update."""
        self.network.load_state_dict(state["weights"])
        self.optimizer.load_state_dict(state["optimizer"])
        self.generator.set_state(state["generator"])
        self.decisions = self.learned = state["learned"]
        self.updates = state["updates"]
        self.episode = state["episode"]
        self.rounds = state["rounds"]
        self.map_counts = dict(state["map_counts"])
        self.results = [EpisodeResult(**row) for row in state["results"]]
        self.best_score = state["best_score"]
        self.best_episode = state["best_episode"]
        self.best_by_map = dict(state.get("best_by_map", {}))
        self.saved = list(state["saved"])
        self.saved_at = state["saved_at"]
        if self.teacher and state.get("curriculum"):
            self.teacher.state = CurriculumState.from_dict(state["curriculum"])

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
            self.teacher.state.level + 1 if self.teacher else "",
            self.games,
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
            "suite": (
                {"name": self.suite.name, "version": self.suite.version}
                if self.suite
                else None
            ),
            "first_seed": self.first_seed,
            "games": self.count.most,  # at most, at once (step 8)
            "stage": world.resource(Stage).to_dict(),  # a mix's first map
            "mix": (
                {
                    "name": self.mix.name,
                    "stages": [stage.to_dict() for stage in self.stages],
                }
                if self.mix
                else None
            ),
            "curriculum": (
                {
                    "spec": self.teacher.curriculum.to_dict(),
                    "level_maps": self.teacher.level_maps,
                    "heuristic": self.teacher.heuristic,
                    "start_level": self.teacher.state.level + 1,
                }
                if self.teacher
                else None
            ),
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
        record(
            self.agent.folder,
            "phase_ended",
            run=self.folder.name,
            interrupted=interrupted,
            decisions=summary.agent_decisions,
            episodes=summary.episodes,
            seconds=summary.seconds,
            mean_score=round(summary.mean_score, 1),
            survival_rate=round(summary.survival_rate, 4),
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
