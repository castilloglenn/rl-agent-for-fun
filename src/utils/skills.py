"""The default suite's skills, and their shares of the heuristic's score
(roadmap 7d3b, 7d4). No torch: the control center reads it too.

A skill's share is its value over the heuristic's on it, the heuristic's
counted as at least the skill's floor (100 game points for a round, 0.1
for braking), so a skill the heuristic can't do can't divide by about 0.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from src.utils import named_files

SUITE = "skills"  # the default suite
FLOORS = {"round": 100.0, "braking": 0.1}
COLUMN = "skill:"  # a skill's column in results: "skill:open_field"


@dataclass(frozen=True)
class Skill:
    name: str
    label: str
    group: str
    kind: str
    stage: str
    floor: float | None = None

    @property
    def column(self) -> str:
        return COLUMN + self.name

    @property
    def minimum(self) -> float:
        """The least the heuristic's value counts as, for a share."""
        return FLOORS[self.kind] if self.floor is None else self.floor


def scenarios(name: str = SUITE, root: Path = named_files.REPO) -> list:
    """The suite file's scenarios, as plain data ([] if it's missing)."""
    try:
        data = json.loads(named_files.find("suites", name, root).read_text())
    except (FileNotFoundError, ValueError):
        return []
    return data.get("scenarios", [])


def load(name: str = SUITE, root: Path = named_files.REPO) -> list[Skill]:
    """The suite's skills, in its order."""
    return [
        Skill(
            s["name"],
            s.get("label") or s["name"],
            s.get("group", ""),
            s["kind"],
            s["stage"],
            s.get("floor"),
        )
        for s in scenarios(name, root)
    ]


def shares(values: dict, heuristic: dict, skills) -> dict[str, float]:
    """Each skill's value as a share of the heuristic's (1.0: as good as
    the heuristic). `values` and `heuristic` are keyed by column; `skills`
    is any list with `name`, `column`, and `minimum` (a Skill, or the
    evaluation's Scenario). A skill missing from either is left out.
    """
    found = {}
    for skill in skills:
        value = values.get(skill.column)
        base = heuristic.get(skill.column)
        if value is not None and base is not None:
            found[skill.name] = value / max(base, skill.minimum)
    return found
