"""The Maps tab's data (roadmap step 7c3): every stage in stages/, what
uses it (runs that played on it, suites that score on it), and copying
or deleting one.

A map is protected, so it can't be deleted, when the code relies on it
(the box, the default) or a suite plays on it.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.control import runs
from src.editor.model import NAME, dump_stage
from src.render.camera import fit_scale

REPO = Path(__file__).resolve().parents[2]
DEFAULT = "box"


class MapError(ValueError):
    pass


@dataclass
class MapInfo:
    name: str
    data: dict  # the stage file
    modified: float  # the file's time, for sorting by newest
    suites: list[str] = field(default_factory=list)
    # Who played on it: (agent or driver, run kind) -> runs.
    played: dict = field(default_factory=dict)

    @property
    def size(self) -> tuple[float, float]:
        return tuple(self.data.get("size", (0, 0)))

    @property
    def walls(self) -> int:
        return len(self.data.get("walls", []))

    @property
    def checkpoints(self) -> dict:
        return self.data.get("checkpoints", {})

    @property
    def big(self) -> bool:
        """Bigger than the game's view: it's followed, with a map card."""
        width, height = self.size
        return bool(width and height) and fit_scale(width, height) < 1

    @property
    def default(self) -> bool:
        return self.name == DEFAULT

    @property
    def protected(self) -> str:
        """Why it can't be deleted ("" if it can)."""
        if self.default:
            return "the default map: the code relies on it"
        if self.suites:
            return f"a suite plays on it: {', '.join(self.suites)}"
        return ""

    @property
    def runs(self) -> int:
        return sum(self.played.values())

    def badges(self) -> list[str]:
        found = []
        if self.default:
            found.append("DEFAULT")
        if self.suites:
            found.append("SUITE")
        if self.big:
            found.append("BIG")
        return found


def load_maps(
    root: Path | None = None, runs_dir: Path | None = None
) -> list[MapInfo]:
    """Every stage file, with what uses it, by name."""
    root = root or REPO
    found = []
    for path in sorted((root / "stages").glob("*.json")):
        data = runs.read_json(path)
        if not data:
            continue
        found.append(MapInfo(path.stem, data, path.stat().st_mtime))
    by_name = {m.name: m for m in found}
    for suite in sorted((root / "suites").glob("*.json")):
        for scenario in runs.read_json(suite).get("scenarios", []):
            info = by_name.get(scenario.get("stage"))
            if info and suite.stem not in info.suites:
                info.suites.append(suite.stem)
    for folder in (runs_dir or runs.RUNS_DIR).glob("*/"):
        config = runs.read_json(folder / "config.json")
        stage = (config.get("stage") or {}).get("name")
        info = by_name.get(stage)
        if not info:
            continue
        key = (runs.run_who(config), runs.run_kind(config))
        info.played[key] = info.played.get(key, 0) + 1
    return found


def sort_maps(maps: list[MapInfo], by: str) -> list[MapInfo]:
    keys = {
        "name": lambda m: m.name.lower(),
        "newest": lambda m: -m.modified,
        "walls": lambda m: (-m.walls, m.name.lower()),
    }
    return sorted(maps, key=keys[by])


def check_new_name(root: Path, name: str) -> str:
    """A new map's name, stripped. Raises MapError if it can't be used."""
    name = name.strip()
    if not NAME.match(name):
        raise MapError("a map's name uses letters, digits, - and _ only")
    if (root / "stages" / f"{name}.json").exists():
        raise MapError(f"stages/{name}.json already exists")
    return name


def duplicate(root: Path, name: str, new: str) -> Path:
    """A copy of the map under a new name (its `name` set to it)."""
    new = check_new_name(root, new)
    data = json.loads((root / "stages" / f"{name}.json").read_text())
    data["name"] = new
    target = root / "stages" / f"{new}.json"
    target.write_text(dump_stage(data))
    return target
