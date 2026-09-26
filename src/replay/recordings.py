"""Your recorded demo rounds, per player.

    recordings/<player>/          the latest rounds (oldest removed past 50)
    recordings/<player>/kept/     rounds you kept (K): never removed

Kept rounds are the natural dataset for an imitation agent (roadmap 5b).
"""

import re
from datetime import datetime
from pathlib import Path

from src.replay.format import Replay, write_replay
from src.replay.recorder import ReplayRecorder

RECORDINGS_DIR = Path(__file__).resolve().parents[2] / "recordings"
KEEP_LATEST = 50
MIN_STEPS = 120  # shorter rounds (under 1 s) aren't saved


def _age_order(path: Path) -> tuple:
    """Oldest first: by save time, then by name (same-second saves)."""
    return (path.stat().st_mtime_ns, path.name)


def folder_name(player: str) -> str:
    """A safe folder name for a player ("You" stays "You")."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", player).strip("_") or "player"


class RecordingLibrary:
    def __init__(
        self,
        player: str,
        root: Path | None = None,
        limit: int = KEEP_LATEST,
        min_steps: int = MIN_STEPS,
    ) -> None:
        self.folder = (root or RECORDINGS_DIR) / folder_name(player)
        self.kept_folder = self.folder / "kept"
        self.limit = limit
        self.min_steps = min_steps

    def save(self, replay: Replay) -> Path | None:
        """Saves a finished replay. Returns its path, or None if it was too
        short to keep.
        """
        end = replay.end or {}
        if end.get("step", 0) < self.min_steps:
            return None
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        score = end.get("scores", {}).get("1", 0)
        name = (
            f"{stamp}_seed{replay.header['seed']}"
            f"_score{score:.0f}_{end.get('reason')}"
        )
        path = self.folder / f"{name}.jsonl.gz"
        suffix = 1
        while path.exists():
            suffix += 1
            path = self.folder / f"{name}_{suffix}.jsonl.gz"
        write_replay(replay, path)
        self.prune()
        return path

    def keep(self, path: Path) -> Path:
        """Moves a recording into kept/, where it's never removed."""
        self.kept_folder.mkdir(parents=True, exist_ok=True)
        kept = self.kept_folder / path.name
        path.rename(kept)
        return kept

    def recent(self) -> list[Path]:
        """Not-kept recordings, oldest first."""
        return sorted(self.folder.glob("*.jsonl*"), key=_age_order)

    def kept(self) -> list[Path]:
        return sorted(self.kept_folder.glob("*.jsonl*"), key=_age_order)

    def prune(self) -> None:
        """Removes the oldest not-kept recordings beyond the limit."""
        recent = self.recent()
        for path in recent[: max(0, len(recent) - self.limit)]:
            path.unlink()


class LibraryRecorder(ReplayRecorder):
    """Records every round and saves it to a library: when the round ends,
    and when it's cut short (restart or quit) as "stopped".
    """

    def __init__(self, drivers: dict, library: RecordingLibrary) -> None:
        super().__init__(drivers)
        self.library = library
        self.last_saved: Path | None = None
        self.last_kept: bool = False

    def on_finish(self, env, reason: str | None = None) -> None:
        super().on_finish(env, reason)
        path = self.library.save(self.replay)
        if path:
            self.last_saved, self.last_kept = path, False

    def on_before_reset(self, env) -> None:
        if self.replay is not None and not self.finished:
            self.on_finish(env, "stopped")

    def keep_last(self) -> Path | None:
        """Keeps the latest saved recording (K). Returns its new path."""
        if self.last_saved is None or self.last_kept:
            return None
        self.last_saved = self.library.keep(self.last_saved)
        self.last_kept = True
        return self.last_saved


def list_recordings(root: Path | None = None) -> list[dict]:
    """One row per player: counts, and the newest recording."""
    rows = []
    for folder in sorted((root or RECORDINGS_DIR).glob("*/")):
        library = RecordingLibrary(folder.name, root=root)
        everything = library.recent() + library.kept()
        if not everything:
            continue
        rows.append(
            {
                "player": folder.name,
                "recent": len(library.recent()),
                "kept": len(library.kept()),
                "newest": max(everything, key=_age_order).name,
            }
        )
    return rows


def format_recordings(rows: list[dict]) -> str:
    if not rows:
        return "No recordings yet. Drive with: make maze_car"
    lines = [f"{'player':16s} {'recent':>6s} {'kept':>5s}  newest"]
    for row in rows:
        lines.append(
            f"{row['player'][:16]:16s} {row['recent']:>6d} "
            f"{row['kept']:>5d}  {row['newest']}"
        )
    return "\n".join(lines)


def latest_recording(root: Path | None = None) -> Path:
    """The newest recording of any player (kept or not)."""
    files = list((root or RECORDINGS_DIR).glob("*/*.jsonl*"))
    files += list((root or RECORDINGS_DIR).glob("*/kept/*.jsonl*"))
    if not files:
        raise FileNotFoundError("no recordings yet: drive with make maze_car")
    return max(files, key=_age_order)
