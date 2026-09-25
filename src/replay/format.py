"""The replay file format: JSON Lines, optionally gzipped.

    {header}                                   first line
    {"step": 0, "actions": {"1": [...]}}       one line per action change
    ...
    {"end": {...}}                             last line (if finished)

Actions are stored per slot, in the header's `action_names` order, and
only when they change. See docs/decisions/003-replay-over-multi-window.md.
"""

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path

REPLAY_FORMAT = 1


class ReplayError(ValueError):
    pass


@dataclass
class Replay:
    header: dict
    # (step, {slot: [bool, ...]}): the actions from that step on.
    changes: list[tuple[int, dict[str, list[bool]]]] = field(
        default_factory=list
    )
    end: dict | None = None

    @property
    def slots(self) -> dict[str, dict]:
        return self.header["slots"]

    @property
    def action_names(self) -> list[str]:
        return self.header["action_names"]

    def actions_by_step(self, total_steps: int) -> list[dict[str, list]]:
        """Expands the changes into one {slot: actions} per step."""
        current: dict[str, list[bool]] = {}
        changes = iter(self.changes)
        upcoming = next(changes, None)
        expanded = []
        for step in range(total_steps):
            while upcoming is not None and upcoming[0] <= step:
                current = {**current, **upcoming[1]}
                upcoming = next(changes, None)
            expanded.append(current)
        return expanded


def write_replay(replay: Replay, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [replay.header]
    lines += [{"step": step, "actions": acts} for step, acts in replay.changes]
    if replay.end is not None:
        lines.append({"end": replay.end})
    text = "".join(
        json.dumps(line, separators=(",", ":")) + "\n" for line in lines
    )
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as file:
            file.write(text)
    else:
        path.write_text(text, encoding="utf-8")
    return path


def read_replay(path: str | Path) -> Replay:
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as file:
            raw = file.read()
    else:
        raw = path.read_text(encoding="utf-8")
    lines = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if not lines:
        raise ReplayError(f"{path} is empty")

    header = lines[0]
    if header.get("format") != REPLAY_FORMAT:
        raise ReplayError(
            f"unsupported replay format {header.get('format')!r}, "
            f"expected {REPLAY_FORMAT}"
        )
    replay = Replay(header=header)
    for line in lines[1:]:
        if "end" in line:
            replay.end = line["end"]
        else:
            replay.changes.append((line["step"], line["actions"]))
    return replay


def to_current_actions(
    stored: list[bool], stored_names: list[str], current_names: tuple
) -> tuple[bool, ...]:
    """Maps stored actions onto the current action names, by name.

    Names the replay doesn't have count as not pressed. Names the
    current code doesn't know are ignored.
    """
    pressed = dict(zip(stored_names, stored))
    return tuple(bool(pressed.get(name, False)) for name in current_names)
