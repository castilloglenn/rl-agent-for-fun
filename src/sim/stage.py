"""Stage files: the whole playing area as data.

See docs/decisions/009-stage-format-and-spawn-schedules.md.
"""

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from src.utils import named_files

STAGE_FORMAT = 1
STAGES_DIR = Path(__file__).resolve().parents[2] / "stages"
SCHEDULE_MODES = ("random", "scripted")
AT_ONCE = 3  # fuels on the map at once, by default (9a2)
MAX_AT_ONCE = 3
# Where scripted fuels start: the first point, or one picked from
# the seed (7d5a: a training course practices every zone).
STARTS = ("first", "seeded")
# A spawn this close to a wall would start with the car touching it (a
# car is 24 x 16: 14.4 px from its center to a corner).
SPAWN_CLEARANCE = 16.0


class StageError(ValueError):
    pass


@dataclass(frozen=True)
class Spawn:
    x: float
    y: float
    angle: float = 0.0


@dataclass(frozen=True)
class FuelRules:
    mode: str = "random"  # "random" (from the seed) or "scripted"
    radius: float = 15.0
    border_margin: float = 40.0  # random mode: px inside the border
    min_car_distance: float = 100.0  # random mode: px from any car
    points: tuple[tuple[float, float], ...] = ()  # scripted mode, in order
    start: str = "first"  # scripted mode: "first" or "seeded" (STARTS)
    # Fuels on the map at once (9a2): scripted, the next ones in order (a
    # sliding window: taking any brings in the next); random, that many.
    at_once: int = 3

    @property
    def on_map(self) -> int:
        """Fuels out at once: scripted, never more than its points (a
        window wider than the sequence would show a point twice).
        """
        if self.mode == "scripted":
            return min(self.at_once, len(self.points))
        return self.at_once


@dataclass(frozen=True)
class Stage:
    name: str
    width: float
    height: float
    spawns: tuple[Spawn, ...]
    fuel: FuelRules
    walls: tuple = ()  # [x, y, width, height] rectangles (step 7a)
    format: int = STAGE_FORMAT

    @staticmethod
    def from_dict(data: dict) -> "Stage":
        if data.get("format") != STAGE_FORMAT:
            raise StageError(
                f"unsupported stage format {data.get('format')!r}, "
                f"expected {STAGE_FORMAT}"
            )
        width, height = data["size"]
        fuel = dict(data.get("fuel", {}))
        fuel["points"] = tuple(
            tuple(point) for point in fuel.get("points", ())
        )
        stage = Stage(
            name=data["name"],
            width=float(width),
            height=float(height),
            spawns=tuple(Spawn(**spawn) for spawn in data["spawns"]),
            fuel=FuelRules(**fuel),
            walls=tuple(tuple(wall) for wall in data.get("walls", ())),
        )
        stage.validate()
        return stage

    def to_dict(self) -> dict:
        """Plain data, in the file's layout. Replays embed this."""
        fuel = asdict(self.fuel)
        fuel["points"] = [list(p) for p in self.fuel.points]
        if self.fuel.mode != "scripted":
            del fuel["points"]
        if self.fuel.mode != "scripted" or (
            self.fuel.start == "first"
        ):
            del fuel["start"]  # the default: files stay as they were
        if self.fuel.at_once == AT_ONCE:
            del fuel["at_once"]  # the default
        return {
            "format": self.format,
            "name": self.name,
            "size": [self.width, self.height],
            "walls": [list(wall) for wall in self.walls],
            "spawns": [asdict(spawn) for spawn in self.spawns],
            "fuel": fuel,
        }

    def validate(self) -> None:
        from src.sim.walls import Box

        if self.width <= 0 or self.height <= 0:
            raise StageError("stage size must be positive")
        boxes = []
        for wall in self.walls:
            if len(wall) != 4:
                raise StageError(
                    f"wall {list(wall)}: needs x, y, width, height"
                )
            x, y, width, height = wall
            if width <= 0 or height <= 0:
                raise StageError(f"wall {list(wall)}: size must be positive")
            if x < 0 or y < 0 or x + width > self.width or (
                y + height > self.height
            ):
                raise StageError(f"wall {list(wall)} is outside the stage")
            boxes.append(Box.from_list(wall))
        if not self.spawns:
            raise StageError("a stage needs at least one spawn")
        for spawn in self.spawns:
            where = f"({spawn.x:g}, {spawn.y:g})"
            if not self.contains(spawn.x, spawn.y):
                raise StageError(f"the spawn at {where} is outside the stage")
            near = [b.distance(spawn.x, spawn.y) for b in boxes]
            if any(d < SPAWN_CLEARANCE for d in near):
                raise StageError(
                    f"the spawn at {where} is on or next to a wall "
                    f"(keep {SPAWN_CLEARANCE:g} px clear)"
                )
        rules = self.fuel
        if rules.mode not in SCHEDULE_MODES:
            raise StageError(f"unknown fuel mode {rules.mode!r}")
        if rules.start not in STARTS:
            raise StageError(f"unknown fuel start {rules.start!r}")
        if not 1 <= rules.at_once <= MAX_AT_ONCE:
            raise StageError(
                f"fuel at_once is 1 to {MAX_AT_ONCE}, not {rules.at_once}"
            )
        if rules.mode == "scripted":
            if not rules.points:
                raise StageError("scripted fuel needs points")
            for x, y in rules.points:
                if not self.contains(x, y):
                    raise StageError(f"fuel ({x:g}, {y:g}) is outside")
                if any(b.distance(x, y) < rules.radius for b in boxes):
                    raise StageError(
                        f"fuel ({x:g}, {y:g}) touches a wall"
                    )
        elif 2 * rules.border_margin >= min(self.width, self.height):
            raise StageError("fuel border_margin leaves no room")

    def with_at_once(self, fuels: int) -> "Stage":
        """This stage with `fuels` on the map at once (tests, and 9d's
        skills that test one fuel at a time).
        """
        return replace(self, fuel=replace(self.fuel, at_once=fuels))

    def contains(self, x: float, y: float) -> bool:
        return 0 <= x <= self.width and 0 <= y <= self.height


def load_stage(name_or_path: str) -> Stage:
    """A stage by name (stages/<name>.json) or by file path."""
    path = named_files.path_of("stages", name_or_path)
    return Stage.from_dict(json.loads(path.read_text()))
