"""Curricula (roadmap 7f5, decision 063): training that moves itself up
levels, easy to hard, keeping earlier maps in the mix against forgetting.

    curricula/<name>.json  {"format": 1, "name": "skills",
                            "earlier_share": 0.25, "window": 20,
                            "levels": [{"mix": "skill_training_easy",
                                        "goal": 1.0,
                                        "min_decisions": 200000,
                                        "max_decisions": 1500000}, ...]}

A level is a mix (or one stage). It's judged on its own training maps,
never the skills suite's test maps: on each map, the agent's checkpoints
per minute over its last `window` episodes there, as a share of the
heuristic's on that map (at least FLOOR a minute, so a map the heuristic
can't do doesn't divide by about 0). It moves up when every map reaches
the level's goal and has leveled off (the last window no better than
PLATEAU times the one before), after `min_decisions` in the level; or
after `max_decisions` anyway. The last level is where it stays.

Episodes take turns by share: the level's maps share 1 - earlier_share,
maps only earlier levels had share earlier_share, each group evenly. The
next map is the one furthest behind its share: deterministic, so resume
is exact (the state is saved).

No torch here: the control center reads it too.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.utils import mixes, named_files

CURRICULUM_FORMAT = 1
KIND = "curricula"
FLOOR = 1.0  # checkpoints a minute: the least the heuristic counts as
PLATEAU = 1.02  # no more than 2 % better than the window before: leveled


class CurriculumError(ValueError):
    pass


@dataclass(frozen=True)
class Level:
    mix: str  # a mix or a stage
    goal: float = 1.0  # share of the heuristic's rate, on every map
    min_decisions: int = 200_000
    max_decisions: int | None = None  # None: no cap (the last level)


@dataclass(frozen=True)
class Curriculum:
    name: str
    levels: tuple[Level, ...]
    earlier_share: float = 0.25
    window: int = 20  # episodes per map in a smoothed rate
    description: str = ""

    @staticmethod
    def from_dict(data: dict) -> "Curriculum":
        if data.get("format") != CURRICULUM_FORMAT:
            raise CurriculumError(
                f"unsupported curriculum format {data.get('format')!r}"
            )
        levels = data.get("levels")
        if not isinstance(levels, list) or not levels:
            raise CurriculumError("a curriculum needs a list of levels")
        found = []
        for level in levels:
            if not isinstance(level, dict) or not level.get("mix"):
                raise CurriculumError("each level names a mix or a stage")
            found.append(Level(**level))
        share = data.get("earlier_share", 0.25)
        if not 0 <= share < 1:
            raise CurriculumError("earlier_share is from 0 to under 1")
        window = data.get("window", 20)
        if not isinstance(window, int) or window < 2:
            raise CurriculumError("window is a whole number of 2 or more")
        for level in found:
            if level.goal <= 0 or level.min_decisions < 0:
                raise CurriculumError("goals are above 0, decisions 0 up")
        return Curriculum(
            data["name"],
            tuple(found),
            share,
            window,
            data.get("description", ""),
        )

    def to_dict(self) -> dict:
        return {
            "format": CURRICULUM_FORMAT,
            "name": self.name,
            "description": self.description,
            "earlier_share": self.earlier_share,
            "window": self.window,
            "levels": [
                {
                    "mix": level.mix,
                    "goal": level.goal,
                    "min_decisions": level.min_decisions,
                    **(
                        {"max_decisions": level.max_decisions}
                        if level.max_decisions is not None
                        else {}
                    ),
                }
                for level in self.levels
            ],
        }

    def level_maps(self, root: Path = named_files.REPO) -> list[list[str]]:
        """Each level's maps (a mix's stages, or the stage)."""
        return [mixes.stages_of(level.mix, root) for level in self.levels]

    def all_maps(self, root: Path = named_files.REPO) -> list[str]:
        """Every map of every level, once each, in order of appearance."""
        found: list[str] = []
        for maps in self.level_maps(root):
            found += [m for m in maps if m not in found]
        return found

    def check(self, root: Path = named_files.REPO) -> None:
        for level in self.levels:
            try:
                mixes.stages_of(level.mix, root)
            except mixes.MixError as error:
                raise CurriculumError(str(error))
            known = set(named_files.names("stages", root))
            for stage in mixes.stages_of(level.mix, root):
                if stage not in known:
                    raise CurriculumError(
                        f"curriculum {self.name!r}: no stage {stage!r}"
                    )


def is_curriculum(name: str, root: Path = named_files.REPO) -> bool:
    """`name` is a curriculum (a stage or a mix of that name wins)."""
    names = named_files.names
    return (
        name in names(KIND, root)
        and name not in names("stages", root)
        and name not in names(mixes.KIND, root)
    )


def load_curriculum(name: str, root: Path = named_files.REPO) -> Curriculum:
    try:
        data = json.loads(named_files.find(KIND, name, root).read_text())
    except FileNotFoundError as error:
        raise CurriculumError(str(error))
    curriculum = Curriculum.from_dict(data)
    curriculum.check(root)
    return curriculum


@dataclass
class CurriculumState:
    """Where a training is in its curriculum: the level (0-based), when
    it started (the phase's learned decisions), each map's episodes in
    this level, and each map's recent rates (checkpoints a minute).
    """

    level: int = 0
    started: int = 0
    counts: dict = field(default_factory=dict)
    rates: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "started": self.started,
            "counts": dict(self.counts),
            "rates": {k: list(v) for k, v in self.rates.items()},
        }

    @staticmethod
    def from_dict(data: dict) -> "CurriculumState":
        return CurriculumState(
            data["level"],
            data["started"],
            dict(data["counts"]),
            {k: list(v) for k, v in data["rates"].items()},
        )


class Teacher:
    """Runs a curriculum: which map each episode plays, what it scored,
    and when to move up. `heuristic`: the heuristic's checkpoints a
    minute on each map (under the phase's rules).
    """

    def __init__(
        self,
        curriculum: Curriculum,
        level_maps: list[list[str]],
        heuristic: dict[str, float],
        state: CurriculumState | None = None,
    ) -> None:
        self.curriculum = curriculum
        self.level_maps = level_maps
        self.heuristic = heuristic
        self.state = state or CurriculumState()

    @property
    def level(self) -> Level:
        return self.curriculum.levels[self.state.level]

    @property
    def last_level(self) -> bool:
        return self.state.level == len(self.curriculum.levels) - 1

    def shares(self) -> dict[str, float]:
        """Each map's share of the episodes at this level."""
        current = self.level_maps[self.state.level]
        earlier = [
            m
            for maps in self.level_maps[: self.state.level]
            for m in maps
            if m not in current
        ]
        earlier = list(dict.fromkeys(earlier))
        rest = self.curriculum.earlier_share if earlier else 0.0
        found = {m: (1 - rest) / len(current) for m in current}
        for m in earlier:
            found[m] = rest / len(earlier)
        return found

    def next_map(self) -> str:
        """The map furthest behind its share (ties: the first)."""
        shares = self.shares()
        played = sum(self.state.counts.get(m, 0) for m in shares)
        return max(
            shares,
            key=lambda m: shares[m] * (played + 1)
            - self.state.counts.get(m, 0),
        )

    def played(self, stage: str, checkpoints: int, minutes: float) -> None:
        """An episode on `stage` ended."""
        self.state.counts[stage] = self.state.counts.get(stage, 0) + 1
        rates = self.state.rates.setdefault(stage, [])
        rates.append(checkpoints / max(minutes, 1e-6))
        del rates[: -2 * self.curriculum.window]  # two windows kept

    def progress(self) -> dict[str, float | None]:
        """Each level map's smoothed share of the heuristic's rate (None:
        not enough episodes there yet).
        """
        window = self.curriculum.window
        found = {}
        for stage in self.level_maps[self.state.level]:
            rates = self.state.rates.get(stage, [])
            if len(rates) < window:
                found[stage] = None
                continue
            mean = sum(rates[-window:]) / window
            found[stage] = mean / max(self.heuristic.get(stage, 0.0), FLOOR)
        return found

    def _leveled_off(self) -> bool:
        window = self.curriculum.window
        for stage in self.level_maps[self.state.level]:
            rates = self.state.rates.get(stage, [])
            if len(rates) < 2 * window:
                return False
            recent = sum(rates[-window:]) / window
            before = sum(rates[-2 * window : -window]) / window
            if recent > before * PLATEAU:
                return False  # still improving
        return True

    def check(self, learned: int) -> str | None:
        """Moves up a level if it's time: why ("goal" or "cap"), or None.
        `learned`: the phase's decisions so far.
        """
        if self.last_level:
            return None
        level, spent = self.level, learned - self.state.started
        why = None
        if level.max_decisions is not None and spent >= level.max_decisions:
            why = "cap"
        elif spent >= level.min_decisions:
            shares = self.progress()
            reached = all(
                share is not None and share >= level.goal
                for share in shares.values()
            )
            if reached and self._leveled_off():
                why = "goal"
        if why:
            self.state = CurriculumState(self.state.level + 1, learned)
        return why
