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
