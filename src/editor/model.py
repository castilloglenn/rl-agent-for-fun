"""The map editor's model (roadmap step 7c1): a stage file being edited,
with no drawing. Every change is checked by the game's own Stage
validation, and saving writes the stage file.

    tools: select (V), wall (W), spawn (P), checkpoint (C)
    positions snap to a 10 px grid (G turns it off)
    undo and redo keep a snapshot of the stage after each change
"""

import json
import math
import re
from pathlib import Path

from src.sim.stage import Stage, StageError
from src.utils import named_files

NAME = re.compile(r"^[A-Za-z0-9_-]+$")  # a stage's name
BUILT_IN = "a built-in map ships with the app: save it as a new name"
GRID = 10  # px: positions snap to it
SPAWN_TURN = 15  # degrees per Q, E, or mouse wheel notch
MIN_STAGE = 200  # px: the smallest stage side
SPAWN_ROOM = 16  # px the spawn keeps from the stage's edge (its clearance)
SPAWN_PICK = 16  # px around the spawn that selects it
CHECKPOINT_PICK = 6  # px beyond a checkpoint's radius that selects it
TOOLS = ("select", "wall", "spawn", "checkpoint")
RANDOM_CHECKPOINTS = {
    "mode": "random",
    "radius": 15,
    "border_margin": 40,
    "min_car_distance": 100,
}


def new_stage(name: str) -> dict:
    """A new stage: the box's size, spawn, and checkpoint rules."""
    return {
        "format": 1,
        "name": name,
        "size": [855, 480],
        "walls": [],
        "spawns": [{"x": 213.75, "y": 240, "angle": 0}],
        "checkpoints": dict(RANDOM_CHECKPOINTS),
    }


def dump_stage(data: dict) -> str:
    """A stage file's text: the walls one per line, the rest compact
    (the layout of the files in stages/).
    """

    def inline(value) -> str:
        return json.dumps(value)

    walls = data.get("walls", [])
    if walls:
        rows = ",\n".join(f"    {inline(wall)}" for wall in walls)
        walls_text = f"[\n{rows}\n  ]"
    else:
        walls_text = "[]"
    checkpoints = ",\n".join(
        f"    {inline(key)}: {inline(value)}"
        for key, value in data["checkpoints"].items()
    )
    lines = [
        f'  "format": {inline(data["format"])}',
        f'  "name": {inline(data["name"])}',
        f'  "size": {inline(data["size"])}',
        f'  "walls": {walls_text}',
        f'  "spawns": {inline(data["spawns"])}',
        f'  "checkpoints": {{\n{checkpoints}\n  }}',
    ]
    return "{\n" + ",\n".join(lines) + "\n}\n"


def snap(value: float, on: bool = True) -> float:
    """To the grid (a whole number of px), or as is."""
    if not on:
        return round(value, 1)
    return int(round(value / GRID) * GRID)


def _number(value: float):
    """Whole px as ints, so the file reads 570, not 570.0."""
    return int(value) if float(value).is_integer() else value


class EditorModel:
    def __init__(self, name: str, root: Path | None = None) -> None:
        """`root`: where stages/ and user/ are (tests use a scratch
        folder). A map of yours saves where it is, and a new one goes to
        user/stages/. A built-in one only saves as a new name (save_as).
        """
        root = root or named_files.REPO
        self.root = root
        self.built_in = named_files.is_built_in("stages", name, root)
        try:
            self.path = named_files.find("stages", name, root)
        except FileNotFoundError:
            folder = named_files.user_folder("stages", root)
            self.path = folder / f"{name}.json"
        self.folder = self.path.parent
        self.is_new = not self.path.exists()
        if self.is_new:
            self.stage = new_stage(name)
        else:
            self.stage = json.loads(self.path.read_text())
        self.saved = json.dumps(self.stage)  # the file's content
        self.tool = "select"
        self.snapping = True
        self.selection: tuple[str, int] | None = None
        self._history = [json.dumps(self.stage)]
        self._at = 0
        self._points = list(self.stage["checkpoints"].get("points", []))

    # State

    @property
    def name(self) -> str:
        return self.stage["name"]

    @property
    def size(self) -> tuple[float, float]:
        return tuple(self.stage["size"])

    @property
    def walls(self) -> list:
        return self.stage["walls"]

    @property
    def spawn(self) -> dict:
        return self.stage["spawns"][0]

    @property
    def checkpoints(self) -> dict:
        return self.stage["checkpoints"]

    @property
    def points(self) -> list:
        return self.checkpoints.get("points", [])

    @property
    def dirty(self) -> bool:
        return self.is_new or json.dumps(self.stage) != self.saved

    def problem(self) -> str | None:
        """What the game would refuse about this stage, or None."""
        try:
            Stage.from_dict(self.stage)
        except (StageError, TypeError, KeyError, ValueError) as error:
            return str(error)
        return None

    # History: a snapshot after each change

    def commit(self) -> None:
        """Records the stage as it is now (after a change)."""
        snapshot = json.dumps(self.stage)
        if snapshot == self._history[self._at]:
            return
        del self._history[self._at + 1 :]
        self._history.append(snapshot)
        self._at += 1

    def undo(self) -> bool:
        if self._at == 0:
            return False
        self._at -= 1
        self._restore()
        return True

    def redo(self) -> bool:
        if self._at == len(self._history) - 1:
            return False
        self._at += 1
        self._restore()
        return True

    def _restore(self) -> None:
        self.stage = json.loads(self._history[self._at])
        if self.checkpoints.get("points"):
            self._points = list(self.points)
        if not self._valid_selection():
            self.selection = None

    def _valid_selection(self) -> bool:
        if self.selection is None:
            return True
        kind, index = self.selection
        if kind == "wall":
            return index < len(self.walls)
        if kind == "checkpoint":
            return index < len(self.points)
        return True

    # Finding what's under the mouse (world px; `slack` widens it)

    def pick(self, x: float, y: float, slack: float = 0.0):
        """The thing at (x, y): ("checkpoint", i), ("spawn", 0), or
        ("wall", i), checking the smaller ones first; or None.
        """
        radius = self.checkpoints.get("radius", 15)
        for i, (px, py) in enumerate(self.points):
            if math.dist((x, y), (px, py)) <= radius + CHECKPOINT_PICK + slack:
                return ("checkpoint", i)
        spawn = self.spawn
        if math.dist((x, y), (spawn["x"], spawn["y"])) <= SPAWN_PICK + slack:
            return ("spawn", 0)
        for i in reversed(range(len(self.walls))):  # the last drawn: on top
            wx, wy, ww, wh = self.walls[i]
            if wx - slack <= x <= wx + ww + slack and (
                wy - slack <= y <= wy + wh + slack
            ):
                return ("wall", i)
        return None

    def corner_at(self, x: float, y: float, slack: float):
        """The selected wall's corner at (x, y): 0 top left, 1 top right,
        2 bottom right, 3 bottom left; or None.
        """
        if not self.selection or self.selection[0] != "wall":
            return None
        wx, wy, ww, wh = self.walls[self.selection[1]]
        corners = ((wx, wy), (wx + ww, wy), (wx + ww, wy + wh), (wx, wy + wh))
        for i, (cx, cy) in enumerate(corners):
            if abs(x - cx) <= slack and abs(y - cy) <= slack:
                return i
        return None

    def stage_edge_at(self, x: float, y: float, slack: float):
        """The stage's resizable edge at (x, y): "corner" (bottom right),
        "right", or "bottom"; or None. The top left stays at (0, 0).
        """
        width, height = self.size
        near_right = abs(x - width) <= slack and -slack <= y <= height + slack
        near_bottom = abs(y - height) <= slack and -slack <= x <= width + slack
        if near_right and near_bottom:
            return "corner"
        if near_right:
            return "right"
        if near_bottom:
            return "bottom"
        return None

    def content_size(self) -> tuple[float, float]:
        """The smallest stage that keeps everything inside: the walls,
        the spawn with its clearance, and the checkpoints, at least
        MIN_STAGE.
        """
        right = bottom = MIN_STAGE
        for x, y, w, h in self.walls:
            right, bottom = max(right, x + w), max(bottom, y + h)
        spawn = self.spawn
        right = max(right, spawn["x"] + SPAWN_ROOM)
        bottom = max(bottom, spawn["y"] + SPAWN_ROOM)
        radius = self.checkpoints.get("radius", 15)
        for x, y in self.points:
            right, bottom = max(right, x + radius), max(bottom, y + radius)
        return right, bottom

    def resize_stage(self, edge: str, x: float, y: float) -> None:
        """Drags the stage's right edge, bottom edge, or bottom right
        corner to (x, y), snapped, never cutting off what's inside.
        """
        width, height = self.size
        least_w, least_h = self.content_size()
        if edge in ("right", "corner"):
            width = max(snap(x, self.snapping), least_w)
        if edge in ("bottom", "corner"):
            height = max(snap(y, self.snapping), least_h)
        self.stage["size"] = [_number(width), _number(height)]

    # Edits (each caller commits when the gesture ends)

    def add_wall(self, x0: float, y0: float, x1: float, y1: float) -> bool:
        """A wall between two corners (snapped). False if it's empty."""
        x0, x1 = sorted((snap(x0, self.snapping), snap(x1, self.snapping)))
        y0, y1 = sorted((snap(y0, self.snapping), snap(y1, self.snapping)))
        width, height = self._clamp_size(x0, y0, x1 - x0, y1 - y0)
        if width <= 0 or height <= 0:
            return False
        self.walls.append([_number(x0), _number(y0), width, height])
        self.selection = ("wall", len(self.walls) - 1)
        return True

    def _clamp_size(self, x, y, width, height):
        stage_width, stage_height = self.size
        width = min(width, stage_width - x)
        height = min(height, stage_height - y)
        return _number(width), _number(height)

    def move_wall(self, index: int, x: float, y: float) -> None:
        """The wall's top left to (x, y), snapped, inside the stage."""
        _, _, width, height = self.walls[index]
        stage_width, stage_height = self.size
        x = min(max(snap(x, self.snapping), 0), stage_width - width)
        y = min(max(snap(y, self.snapping), 0), stage_height - height)
        self.walls[index][:2] = [_number(x), _number(y)]

    def resize_wall(self, index: int, corner: int, x: float, y: float):
        """Drags one corner to (x, y), snapped; the opposite one stays."""
        wx, wy, ww, wh = self.walls[index]
        left, top, right, bottom = wx, wy, wx + ww, wy + wh
        x, y = snap(x, self.snapping), snap(y, self.snapping)
        stage_width, stage_height = self.size
        x = min(max(x, 0), stage_width)
        y = min(max(y, 0), stage_height)
        if corner in (0, 3):
            left = min(x, right - 1)
        else:
            right = max(x, left + 1)
        if corner in (0, 1):
            top = min(y, bottom - 1)
        else:
            bottom = max(y, top + 1)
        self.walls[index] = [
            _number(left),
            _number(top),
            _number(right - left),
            _number(bottom - top),
        ]

    def move_spawn(self, x: float, y: float) -> None:
        stage_width, stage_height = self.size
        x = min(max(snap(x, self.snapping), 0), stage_width)
        y = min(max(snap(y, self.snapping), 0), stage_height)
        self.spawn["x"], self.spawn["y"] = _number(x), _number(y)

    def turn_spawn(self, degrees: float) -> None:
        self.spawn["angle"] = _number((self.spawn["angle"] + degrees) % 360)

    def add_checkpoint(self, x: float, y: float) -> None:
        """The next scripted checkpoint (scripted mode from now on)."""
        self._scripted()
        point = [
            _number(snap(x, self.snapping)),
            _number(snap(y, self.snapping)),
        ]
        self.points.append(point)
        self._points = list(self.points)
        self.selection = ("checkpoint", len(self.points) - 1)

    def move_checkpoint(self, index: int, x: float, y: float) -> None:
        stage_width, stage_height = self.size
        self.points[index] = [
            _number(min(max(snap(x, self.snapping), 0), stage_width)),
            _number(min(max(snap(y, self.snapping), 0), stage_height)),
        ]
        self._points = list(self.points)

    def toggle_checkpoint_mode(self) -> None:
        """Random (from the seed) or scripted (the points, in order). The
        points come back when switching back to scripted.
        """
        radius = self.checkpoints.get("radius", 15)
        if self.checkpoints.get("mode") == "scripted":
            self._points = list(self.points)
            self.stage["checkpoints"] = {**RANDOM_CHECKPOINTS, "radius": radius}
        else:
            self._scripted()

    def _scripted(self) -> None:
        if self.checkpoints.get("mode") != "scripted":
            radius = self.checkpoints.get("radius", 15)
            self.stage["checkpoints"] = {
                "mode": "scripted",
                "radius": radius,
                "points": list(self._points),
            }

    def delete(self) -> bool:
        """Removes the selection (the spawn stays: a stage needs one)."""
        if not self.selection:
            return False
        kind, index = self.selection
        if kind == "wall":
            del self.walls[index]
        elif kind == "checkpoint":
            del self.points[index]
            self._points = list(self.points)
        else:
            return False
        self.selection = None
        return True

    # Saving

    def save(self) -> str:
        """Writes the stage file. Raises StageError if it isn't valid, or
        if it's built-in (save_as instead).
        """
        if self.built_in:
            raise StageError(BUILT_IN)
        problem = self.problem()
        if problem:
            raise StageError(problem)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path.write_text(dump_stage(self.stage))
        self.saved = json.dumps(self.stage)
        self.is_new = False
        return str(self.path)

    def save_as(self, name: str) -> str:
        """Saves it as a new map of yours named `name` (in user/stages/),
        and goes on editing that one. Raises StageError for a bad or taken
        name, or an invalid stage.
        """
        name = name.strip()
        if not NAME.match(name):
            raise StageError("a map's name uses letters, digits, - and _ only")
        problem = self.problem()
        if problem:
            raise StageError(problem)
        try:
            path = named_files.new_file("stages", name, self.root)
        except FileExistsError as error:
            raise StageError(str(error))
        self.stage["name"] = name
        self.path, self.folder = path, path.parent
        self.built_in, self.is_new = False, True
        # Undo starts over: the old map's steps would bring its name back.
        self._history, self._at = [json.dumps(self.stage)], 0
        return self.save()
