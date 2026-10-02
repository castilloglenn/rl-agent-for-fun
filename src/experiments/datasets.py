"""Imitation datasets: a player's recordings, turned into (observation,
action) samples by re-simulating them (roadmap step 5b).

    datasets/<name>.json   which recordings: player, all or kept, min score

Replays don't store observations: re-simulation (deterministic) rebuilds
them exactly. Agents decide every `action_repeat` steps, so each sample is
the observation at a decision step, labeled with the player's most-pressed
action over that decision's steps. The idle wait before the first key is
left out.
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from src.drivers.actions import CANONICAL_NAMES, canonical_index
from src.replay.format import read_replay
from src.replay.recordings import RECORDINGS_DIR, RecordingLibrary
from src.replay.replayer import Replayer
from src.sim.observation import OBSERVATION_NAMES, OBSERVATION_VERSION
from src.utils import named_files

DATASET_FORMAT = 1
DATASETS_DIR = Path(__file__).resolve().parents[2] / "datasets"
INCLUDE = ("all", "kept")


_SPEED = OBSERVATION_NAMES.index("speed")
_MOVES = {
    i
    for i, name in enumerate(CANONICAL_NAMES)
    if name.split("+")[1] in ("gas", "reverse")
}


class DatasetError(ValueError):
    pass


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    player: str
    include: str = "all"
    min_score: float = 0.0
    description: str = ""
    format: int = DATASET_FORMAT
    # More players' recordings in the same dataset (7g: your corrections
    # with the heuristic's driving, so the fixes don't erase the rest).
    also: tuple[str, ...] = ()
    # How many times a corrected moment counts (7g): a few hundred would
    # be lost among the heuristic's hundred thousand.
    correction_weight: int = 10

    @staticmethod
    def from_dict(data: dict) -> "DatasetSpec":
        if data.get("format") != DATASET_FORMAT:
            raise DatasetError(
                f"unsupported dataset format {data.get('format')!r}"
            )
        spec = DatasetSpec(**{**data, "also": tuple(data.get("also", ()))})
        if spec.correction_weight < 1:
            raise DatasetError("correction_weight is a whole number, 1 up")
        if spec.include not in INCLUDE:
            raise DatasetError(
                f"include must be one of {', '.join(INCLUDE)}, "
                f"not {spec.include!r}"
            )
        return spec

    def to_dict(self) -> dict:
        return {
            "format": self.format,
            "name": self.name,
            "description": self.description,
            "player": self.player,
            "include": self.include,
            "min_score": self.min_score,
            "also": list(self.also),
            "correction_weight": self.correction_weight,
        }


def load_dataset_spec(name_or_path: str = "mine") -> DatasetSpec:
    """A dataset by name (datasets/<name>.json) or by file path."""
    path = named_files.path_of("datasets", name_or_path)
    if not path.exists():
        raise DatasetError(f"no dataset file {path}")
    return DatasetSpec.from_dict(json.loads(path.read_text()))


@dataclass
class Round:
    """One recording, as samples."""

    path: Path
    score: float
    ended_by: str
    stage: str
    rules: str
    observations: np.ndarray  # (decisions, observation size), float32
    actions: np.ndarray  # (decisions,) canonical action indices
    rewards: np.ndarray  # (decisions,) reward profile, summed per decision
    weight: int = 1  # how many times each sample counts (7g corrections)


@dataclass
class Dataset:
    spec: DatasetSpec
    rounds: list[Round] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def samples(self) -> int:
        return sum(len(r.actions) for r in self.rounds)

    @property
    def mean_score(self) -> float:
        if not self.rounds:
            return 0.0
        return sum(r.score for r in self.rounds) / len(self.rounds)


def recording_paths(spec: DatasetSpec, root: Path | None = None) -> list[Path]:
    paths = []
    for player in (spec.player, *spec.also):
        library = RecordingLibrary(player, root=root or RECORDINGS_DIR)
        found = library.kept()
        if spec.include == "all":
            found = library.recent() + found
        paths += found
    return paths


def build_dataset(
    spec: DatasetSpec,
    action_repeat: int,
    root: Path | None = None,
    on_round: Callable[[int, int], None] | None = None,
) -> Dataset:
    """Re-simulates every matching recording into samples. Recordings that
    don't verify (for example from older physics) are skipped, with why.
    on_round(i, n): before each recording (it can take a while: 7c16).
    """
    dataset = Dataset(spec)
    paths = recording_paths(spec, root)
    for i, path in enumerate(paths):
        if on_round:
            on_round(i, len(paths))
        replay = read_replay(path)
        end = replay.end or {}
        score = end.get("scores", {}).get("1", 0)
        if replay.header.get("observation_version") != OBSERVATION_VERSION:
            dataset.skipped.append((path, "another observation version"))
            continue
        if score < spec.min_score:
            dataset.skipped.append((path, f"score {score:,.0f} below min"))
            continue
        round_ = _samples(path, replay, action_repeat)
        if not isinstance(round_, str) and end.get("takeovers"):
            round_.weight = spec.correction_weight
        if isinstance(round_, str):
            dataset.skipped.append((path, round_))
        else:
            dataset.rounds.append(round_)
    return dataset


def _samples(path: Path, replay, repeat: int) -> "Round | str":
    replayer = Replayer(replay)
    env = replayer.env
    observations, actions, rewards, starts = [], [], [], []
    window: list[int] = []
    reward = 0.0
    while not replayer.done:
        if replayer.step_index % repeat == 0:
            observations.append(env.last_observation.copy())
            starts.append(replayer.step_index)
        window.append(canonical_index(replayer.next_action()))
        replayer.step()
        reward += env.last_reward
        if len(window) == repeat or replayer.done:
            # The most-pressed action of this decision (ties: the first).
            actions.append(Counter(window).most_common(1)[0][0])
            rewards.append(reward)
            window, reward = [], 0.0
    check = replayer.verify()
    if not check.ok:
        return "doesn't verify: " + "; ".join(check.problems)
    takeovers = (replay.end or {}).get("takeovers")
    if takeovers:
        # Corrections (7g): only the decisions you drove, labelled with
        # your keys, from where the agent had got itself.
        mine = [
            i
            for i, start in enumerate(starts[: len(actions)])
            if any(low <= start < high for low, high in takeovers)
        ]
        if not mine:
            return "no takeover long enough for a decision"
        observations = [observations[i] for i in mine]
        actions = [actions[i] for i in mine]
        rewards = [rewards[i] for i in mine]
    else:
        # The wait before the player's first key is reaction time, not
        # driving: learning it teaches a stopped car to stay stopped.
        idle = canonical_index((False,) * 5)
        first = next(
            (i for i, a in enumerate(actions) if a != idle), None
        )
        if first is None:
            return "no keys pressed"
        observations, actions, rewards = (
            observations[first:],
            actions[first:],
            rewards[first:],
        )
    # Sitting still (stopped, pressing neither gas nor reverse) is left
    # out too: an agent can't pick it (7f6), and it's the stuck habit.
    keep = [
        i
        for i, action in enumerate(actions)
        if observations[i][_SPEED] != 0 or action in _MOVES
    ]
    observations = [observations[i] for i in keep]
    actions = [actions[i] for i in keep]
    rewards = [rewards[i] for i in keep]
    return Round(
        path=path,
        score=replay.end["scores"]["1"],
        ended_by=replay.end["reason"],
        stage=replay.header["stage"]["name"],
        rules=replay.header["rules"]["name"],
        observations=np.array(observations, dtype=np.float32),
        actions=np.array(actions, dtype=np.int64),
        rewards=np.array(rewards, dtype=np.float32),
    )


def format_dataset(dataset: Dataset) -> str:
    spec = dataset.spec
    lines = [
        f"Dataset {spec.name!r}: player {spec.player!r}"
        f"{''.join(f' and {p!r}' for p in spec.also)}, "
        f"{spec.include} recordings, min score {spec.min_score:,.0f}",
        f"  {len(dataset.rounds)} rounds, {dataset.samples:,} samples, "
        f"your mean score {dataset.mean_score:,.0f}",
    ]
    for path, why in dataset.skipped:
        lines.append(f"  skipped {path.name}: {why}")
    if not dataset.rounds:
        lines.append("  Record rounds first: make maze_car (K keeps one)")
    return "\n".join(lines)
