"""Stage files: the whole playing area as data.

See docs/decisions/009-stage-format-and-spawn-schedules.md.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

STAGE_FORMAT = 1
STAGES_DIR = Path(__file__).resolve().parents[2] / "stages"
SCHEDULE_MODES = ("random", "scripted")
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
class CheckpointRules:
    mode: str = "random"  # "random" (from the seed) or "scripted"
    radius: float = 15.0
    border_margin: float = 40.0  # random mode: px inside the border
    min_car_distance: float = 100.0  # random mode: px from any car
    points: tuple[tuple[float, float], ...] = ()  # scripted mode, in order


@dataclass(frozen=True)
class Stage:
    name: str
    width: float
    height: float
    spawns: tuple[Spawn, ...]
    checkpoints: CheckpointRules
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
        checkpoints = dict(data.get("checkpoints", {}))
        checkpoints["points"] = tuple(
            tuple(point) for point in checkpoints.get("points", ())
        )
        stage = Stage(
            name=data["name"],
            width=float(width),
            height=float(height),
            spawns=tuple(Spawn(**spawn) for spawn in data["spawns"]),
            checkpoints=CheckpointRules(**checkpoints),
            walls=tuple(tuple(wall) for wall in data.get("walls", ())),
        )
        stage.validate()
        return stage

    def to_dict(self) -> dict:
        """Plain data, in the file's layout. Replays embed this."""
        checkpoints = asdict(self.checkpoints)
        checkpoints["points"] = [list(p) for p in self.checkpoints.points]
        if self.checkpoints.mode != "scripted":
            del checkpoints["points"]
        return {
            "format": self.format,
            "name": self.name,
            "size": [self.width, self.height],
            "walls": [list(wall) for wall in self.walls],
            "spawns": [asdict(spawn) for spawn in self.spawns],
            "checkpoints": checkpoints,
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
        rules = self.checkpoints
        if rules.mode not in SCHEDULE_MODES:
            raise StageError(f"unknown checkpoint mode {rules.mode!r}")
        if rules.mode == "scripted":
            if not rules.points:
                raise StageError("scripted checkpoints need points")
            for x, y in rules.points:
                if not self.contains(x, y):
                    raise StageError(f"checkpoint ({x:g}, {y:g}) is outside")
                if any(b.distance(x, y) < rules.radius for b in boxes):
                    raise StageError(
                        f"checkpoint ({x:g}, {y:g}) touches a wall"
                    )
        elif 2 * rules.border_margin >= min(self.width, self.height):
            raise StageError("checkpoint border_margin leaves no room")

    def contains(self, x: float, y: float) -> bool:
        return 0 <= x <= self.width and 0 <= y <= self.height


def load_stage(name_or_path: str) -> Stage:
    """A stage by name (stages/<name>.json) or by file path."""
    path = Path(name_or_path)
    if path.suffix != ".json":
        path = STAGES_DIR / f"{name_or_path}.json"
    return Stage.from_dict(json.loads(path.read_text()))
