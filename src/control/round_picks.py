"""Choosing which rounds an imitation teaches (roadmap 7g2, decision 074):
the facts of each round a dataset would read, and which are picked by
default. The rounds picker (`rounds_picker.py`) shows them; the plan
hands the picked ones to `-imitate --recordings`.

Picked by default: every round, but
- one on a test map (the skills suite's maps, not the box): taught there,
  its skill would measure memory, not skill;
- one correcting an agent outside this agent's line (itself and the
  agents it was branched from): fixes to another agent's mistakes.

No torch: reading a round's facts is quick.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from src.control.recordings_data import parse
from src.experiments.datasets import (
    DatasetError,
    load_dataset_spec,
    player_rounds,
)
from src.replay.format import read_replay
from src.utils import test_maps


@dataclass(frozen=True)
class RoundFacts:
    name: str  # the file name, what --recordings takes
    path: Path
    when: str  # "10-04 18:25:36"
    stamp: str  # for sorting, newest first
    stage: str
    watched: str  # "agent_4@d1100k" (a correction), or ""
    watched_agent: str  # "agent_4", or ""
    takeovers: int  # your stretches (a correction), 0 for plain rounds
    yours: float  # seconds you drove: your stretches, or the whole round
    score: float
    ended: str
    test_map: str | None  # the warning, if it's a test map

    @property
    def correction(self) -> bool:
        return bool(self.watched)


class FactsCache:
    """Round facts by file (a replay is read once per change)."""

    def __init__(self) -> None:
        self._found: dict[tuple[Path, float], RoundFacts | None] = {}

    def facts(self, path: Path) -> RoundFacts | None:
        try:
            key = (path, path.stat().st_mtime)
        except OSError:
            return None
        if key not in self._found:
            self._found[key] = read_facts(path)
        return self._found[key]


def read_facts(path: Path) -> RoundFacts | None:
    """A round's facts from its recording, or None if it can't be read."""
    named = parse(path)
    try:
        replay = read_replay(path)
    except (OSError, ValueError, KeyError):
        return None
    header, end = replay.header, replay.end or {}
    stage = (header.get("stage") or {}).get("name", "?")
    slot = (replay.slots or {}).get("1", {})
    watched_agent = slot.get("id", "") if slot.get("type") == "agent" else ""
    checkpoint = slot.get("checkpoint") or ""
    takeovers = end.get("takeovers") or []
    sps = header.get("steps_per_second") or 120
    steps = end.get("step") or 0
    yours = (
        sum(high - low for low, high in takeovers) / sps
        if takeovers
        else steps / sps
    )
    return RoundFacts(
        name=path.name,
        path=path,
        when=named.when if named else path.name[:17],
        stamp=named.stamp if named else path.name,
        stage=stage,
        watched=(
            f"{watched_agent}@{checkpoint}" if watched_agent and takeovers
            else ""
        ),
        watched_agent=watched_agent if takeovers else "",
        takeovers=len(takeovers),
        yours=yours,
        score=end.get("scores", {}).get("1", named.score if named else 0),
        ended=named.ended if named else (end.get("reason") or ""),
        test_map=test_maps.warning(stage),
    )


def dataset_rounds(
    dataset: str, recordings_dir: Path | None, cache: FactsCache
) -> list[RoundFacts]:
    """The rounds of the dataset's own player it would read (its `also`
    players' rounds always count, unchosen), newest first.
    """
    try:
        spec = load_dataset_spec(dataset)
    except (DatasetError, FileNotFoundError):
        return []
    found = [
        cache.facts(path)
        for path in player_rounds(spec, spec.player, recordings_dir)
    ]
    return sorted(
        (f for f in found if f), key=lambda f: f.stamp, reverse=True
    )


def lineage(agent: str, agents_dir: Path) -> set[str]:
    """The agent and every agent it was branched from (`agent` may be
    "agent_4@d1100k", a branch's start).
    """
    found = set()
    name = agent.split("@")[0]
    while name and name not in found:
        found.add(name)
        profile = agents_dir / name / "profile.json"
        try:
            data = json.loads(profile.read_text())
        except (OSError, json.JSONDecodeError):
            break
        name = (data.get("branched_from") or {}).get("agent", "")
    return found


def default_picks(rounds: list[RoundFacts], line: set[str]) -> set[str]:
    """The rounds picked until you change them."""
    return {
        r.name
        for r in rounds
        if not r.test_map
        and not (r.correction and r.watched_agent not in line)
    }


def summary(rounds: list[RoundFacts], picked: set[str]) -> str:
    """"2 of 7 rounds · 13.3 s of your driving"."""
    chosen = [r for r in rounds if r.name in picked]
    seconds = sum(r.yours for r in chosen)
    return (
        f"{len(chosen)} of {len(rounds)} rounds · {seconds:,.1f} s of your "
        "driving"
    )


# The preview (7g3): a round's path, re-played headless


PATH_EVERY = 8  # steps between the path's points


@dataclass(frozen=True)
class RoundPath:
    """Where the car went in a round, and which stretches were yours."""

    stage: dict  # the stage's data, for the mini map
    points: list[tuple[float, float, int]]  # (x, y, step), every PATH_EVERY
    total_steps: int
    takeovers: list[tuple[int, int]]  # [first step, last step + 1)
    steps_per_second: int

    def yours(self, step: int) -> bool:
        return any(low <= step < high for low, high in self.takeovers)

    @property
    def first_takeover(self) -> int | None:
        return self.takeovers[0][0] if self.takeovers else None


def round_path(path: Path) -> RoundPath:
    """Re-plays the round headless (about half a second for a minute)."""
    from src.replay.replayer import Replayer
    from src.sim.components import Transform

    replay = read_replay(path)
    replayer = Replayer(replay)
    env = replayer.env
    points = []

    def note() -> None:
        car = env.world.component(env.car, Transform)
        points.append((car.x, car.y, replayer.step_index))

    note()
    while replayer.step():
        if replayer.step_index % PATH_EVERY == 0:
            note()
    note()
    end = replay.end or {}
    return RoundPath(
        stage=replay.header["stage"],
        points=points,
        total_steps=replayer.total_steps,
        takeovers=[tuple(t) for t in end.get("takeovers") or []],
        steps_per_second=replay.header.get("steps_per_second") or 120,
    )


class PathCache:
    """Round paths, each re-played once in the background: `get` returns
    it when ready, and starts it (None meanwhile). A round that can't be
    re-played gives the reason instead.
    """

    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()
        self._found: dict[Path, RoundPath | str] = {}
        self._busy: set[Path] = set()

    def get(self, path: Path) -> RoundPath | str | None:
        import threading

        with self._lock:
            if path in self._found:
                return self._found[path]
            if path in self._busy:
                return None
            self._busy.add(path)
        threading.Thread(target=self._make, args=(path,), daemon=True).start()
        return None

    def _make(self, path: Path) -> None:
        try:
            found: RoundPath | str = round_path(path)
        except Exception as error:  # noqa: BLE001 - shown, not raised
            found = f"it can't be re-played ({error})"
        with self._lock:
            self._found[path] = found
            self._busy.discard(path)

    def wait(self, path: Path, seconds: float = 30.0) -> RoundPath | str | None:
        """Blocks until it's ready (tests)."""
        import time

        until = time.monotonic() + seconds
        while time.monotonic() < until:
            found = self.get(path)
            if found is not None:
                return found
            time.sleep(0.02)
        return None
