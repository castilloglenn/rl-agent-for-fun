"""The trash (roadmap step 6b3): deleting moves folders here instead of
removing them, since agents/ and runs/ are gitignored and git can't bring
them back. Restoring puts them back; emptying deletes them for good.

    trash/<date>_<time>_run-<folder>/
      trash.json        what it was, where each folder came from, when
      runs/<folder>/    the moved folder, at its path from the repo root

One entry per delete, holding every folder that delete moved, so a
restore puts it all back together. Agents (step 6c) use the same entries.
"""

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.control import runs

REPO = Path(__file__).resolve().parents[2]
TRASH_FORMAT = 1


class TrashError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    name: str  # its folder in trash/
    kind: str  # "run" (6c adds "agent")
    label: str  # what was deleted, for example the run's folder
    created: str
    paths: tuple[str, ...]  # the moved folders, from the repo root

    def describe(self) -> str:
        what = ", ".join(self.paths)
        return f"{self.name}  ({self.kind} {self.label}: {what})"


class Trash:
    def __init__(self, root: Path | None = None) -> None:
        """`root`: the repo (tests use a scratch folder)."""
        self.root = root or REPO
        self.folder = self.root / "trash"
        self.runs_dir = self.root / "runs"

    # Deleting

    def delete_run(self, name: str) -> Entry:
        """Moves a run folder into the trash. The checkpoints it saved stay
        in its agent (later training continues from them).
        """
        folder = self.runs_dir / name
        config = runs._read_json(folder / "config.json")
        if not folder.is_dir() or not config:
            raise TrashError(f"no run {name!r} in {self.runs_dir}")
        status = runs.status_of(folder, runs.run_kind(config), None)
        if status in runs.LIVE:
            raise TrashError(f"{name} is still running: stop it first")
        return self._move("run", name, [folder])

    def _move(self, kind: str, label: str, folders: list[Path]) -> Entry:
        now = datetime.now()
        name = f"{now:%Y-%m-%d_%H%M%S}_{kind}-{label}"
        entry = self.folder / name
        suffix = 2
        while entry.exists():
            entry = self.folder / f"{name}_{suffix}"
            suffix += 1
        paths = [str(f.relative_to(self.root)) for f in folders]
        entry.mkdir(parents=True)
        info = {
            "format": TRASH_FORMAT,
            "kind": kind,
            "label": label,
            "created": now.astimezone().isoformat(timespec="seconds"),
            "paths": paths,
        }
        (entry / "trash.json").write_text(json.dumps(info, indent=2) + "\n")
        for folder, path in zip(folders, paths):
            target = entry / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(folder), str(target))
        return _entry(entry)

    # Looking, restoring, emptying

    def entries(self) -> list[Entry]:
        """Newest first."""
        if not self.folder.exists():
            return []
        found = []
        for folder in sorted(self.folder.glob("*/"), reverse=True):
            entry = _entry(folder)
            if entry:
                found.append(entry)
        return found

    def restore(self, name: str) -> Entry:
        """Puts every folder of an entry back where it was. Refused if
        something now has one of those names.
        """
        folder = self.folder / name
        entry = _entry(folder)
        if not entry:
            raise TrashError(f"no trash entry {name!r}")
        taken = [p for p in entry.paths if (self.root / p).exists()]
        if taken:
            raise TrashError(
                f"can't restore: {', '.join(taken)} exists again. Rename or "
                "delete it first."
            )
        for path in entry.paths:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(folder / path), str(target))
        shutil.rmtree(folder)  # only trash.json and empty folders are left
        return entry

    def empty(self) -> list[Entry]:
        """Deletes every entry for good."""
        gone = self.entries()
        for entry in gone:
            shutil.rmtree(self.folder / entry.name)
        return gone


def _entry(folder: Path) -> Entry | None:
    info = runs._read_json(folder / "trash.json")
    if not info:
        return None
    return Entry(
        name=folder.name,
        kind=info["kind"],
        label=info["label"],
        created=info["created"],
        paths=tuple(info["paths"]),
    )


def format_entries(entries: list[Entry]) -> str:
    if not entries:
        return "The trash is empty."
    lines = [f"{len(entries)} in the trash (newest first):"]
    lines += [f"  {entry.describe()}" for entry in entries]
    lines.append("Restore one: make restore TRASH=<entry>")
    return "\n".join(lines)
