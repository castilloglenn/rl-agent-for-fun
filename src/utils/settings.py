"""Your display settings (roadmap 7c5, decision 040): `user/settings.json`,
out of git. Display only: nothing here changes the simulation, so replays,
runs, and scores never depend on it.

The game window's O box and the control center's Settings tab (7c6) edit
them. A missing file, an unknown key, or a value that isn't one of the
choices falls back to the default, so a hand-edited file can't break a
window.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from src.utils import named_files

SETTINGS_PATH = named_files.REPO / named_files.USER / "settings.json"


@dataclass(frozen=True)
class Option:
    key: str
    group: str
    label: str
    choices: tuple  # ((value, shown), ...): the first is the default

    @property
    def default(self):
        return self.choices[0][0]

    def shown(self, value) -> str:
        return next(text for v, text in self.choices if v == value)


ON_OFF = ((True, "on"), (False, "off"))
OPTIONS = (
    Option("bars", "Car", "Bars", (("above", "above"), ("below", "below"))),
    Option(
        "bars_shown",
        "Car",
        "Bars shown",
        (("always", "always"), ("damaged", "only when damaged")),
    ),
    Option("rays", "Lines", "Rays", ON_OFF),
    Option("hitbox", "Lines", "Hitbox", ON_OFF),
    Option("guide", "Lines", "Checkpoint guide", ON_OFF),
    Option(
        "trail",
        "Lines",
        "Trail (watching, replays)",
        ((False, "off"), (True, "on")),
    ),
    Option(
        "big_stage_camera",
        "Camera",
        "Big stages start in",
        (("follow", "follow"), ("fit", "fit")),
    ),
    Option("map_intro", "Camera", "Map intro", ON_OFF),
    Option(
        "fps_cap",
        "Display",
        "FPS cap",
        ((0, "display's rate"), (60, "60"), (30, "30")),
    ),
)
BY_KEY = {option.key: option for option in OPTIONS}


def _is_choice(value, option: Option) -> bool:
    """Exactly one of its choices (True isn't 1, 60.0 isn't 60)."""
    return any(
        type(value) is type(v) and value == v for v, _ in option.choices
    )


class Settings:
    """The settings' values, and where they're saved (`path`: None keeps
    them in memory only, as tests and headless runs do).
    """

    def __init__(self, values: dict | None = None, path: Path | None = None):
        self.path = Path(path) if path else None
        self.values = {o.key: o.default for o in OPTIONS}
        for key, value in (values or {}).items():
            option = BY_KEY.get(key)
            if option and _is_choice(value, option):
                self.values[key] = value

    @staticmethod
    def load(path: Path | str | None = None) -> "Settings":
        """From `path` (defaults if it's missing or unreadable)."""
        values = {}
        if path:
            try:
                values = json.loads(Path(path).read_text())
            except (OSError, ValueError):
                values = {}
        return Settings(values if isinstance(values, dict) else {}, path)

    def __getitem__(self, key: str):
        return self.values[key]

    def shown(self, key: str) -> str:
        return BY_KEY[key].shown(self.values[key])

    def step(self, key: str, by: int = 1) -> None:
        """The next (or previous) choice of `key`, saved."""
        choices = [v for v, _ in BY_KEY[key].choices]
        at = choices.index(self.values[key])
        self.values[key] = choices[(at + by) % len(choices)]
        self.save()

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.values, indent=2) + "\n")
