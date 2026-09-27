"""The vitals log: the machine's readings while the control center is
open, kept small, for looking into a crash afterwards.

    logs/vitals.csv     the newest rows
    logs/vitals.1.csv   the file before (at most one)

A row every 10 s, and at once when a stat changes level (normal, caution,
danger), so a short spike isn't missed. Job starts and exits, and the
control center opening and quitting, are rows with a note. A log that
ends without "quit" means the control center itself stopped abruptly;
a job that exits with code -9 was killed (often: out of memory).

When the file passes MAX_BYTES it becomes vitals.1.csv, so both together
stay near 200 KB, and the last 100 rows are about 1.5k tokens to read.
"""

import csv
import threading
from datetime import datetime
from pathlib import Path

from src.control.stats import Snapshot

REPO = Path(__file__).resolve().parents[2]
LOGS_DIR = REPO / "logs"
EVERY = 10.0  # seconds between rows
MAX_BYTES = 100_000  # then the file rotates
TAIL_ROWS = 30  # what `make vitals` shows
COLUMNS = (
    "time",
    "cpu",
    "jobs_cpu",
    "mem_gb",
    "mem",
    "jobs_mem_gb",
    "battery",
    "plugged",
    "disk_gb",
    "jobs",
    "note",
)


class VitalsLog:
    def __init__(
        self,
        folder: Path | None = None,
        every: float = EVERY,
        max_bytes: int = MAX_BYTES,
    ) -> None:
        self.folder = folder or LOGS_DIR
        self.path = self.folder / "vitals.csv"
        self.every = every
        self.max_bytes = max_bytes
        self._last: float | None = None  # when the last timed row went in
        self._levels: dict | None = None
        self._snapshot: Snapshot | None = None
        self._lock = threading.Lock()  # job exits are noted from threads

    def record(self, snapshot: Snapshot, now: float) -> bool:
        """A row if `every` seconds passed or a level changed. `now` is a
        monotonic clock. True if it wrote one.
        """
        self._snapshot = snapshot
        levels = snapshot.levels()
        due = self._last is None or now - self._last >= self.every
        changed = self._levels is not None and levels != self._levels
        self._levels = levels
        if not (due or changed):
            return False
        self._last = now
        note = "level change" if changed and not due else ""
        self._write(snapshot, note)
        return True

    def note(self, text: str, snapshot: Snapshot | None = None) -> None:
        """A row with a note, with the latest readings."""
        self._write(snapshot or self._snapshot, text)

    def _write(self, snapshot: Snapshot | None, note: str) -> None:
        with self._lock:
            self._append(row(snapshot, note))

    def _append(self, values: list[str]) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.stat().st_size > self.max_bytes:
            self.path.replace(self.folder / "vitals.1.csv")
        new = not self.path.exists()
        with open(self.path, "a", newline="") as file:
            writer = csv.writer(file)
            if new:
                writer.writerow(COLUMNS)
            writer.writerow(values)


def row(snapshot: Snapshot | None, note: str = "") -> list[str]:
    """Short values: whole percents, GB to one decimal."""
    time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if snapshot is None:
        return [time, *[""] * (len(COLUMNS) - 2), note]
    s = snapshot
    plugged = "" if s.plugged is None else str(int(s.plugged))
    return [
        time,
        f"{s.cpu:.0f}",
        f"{s.jobs_cpu:.0f}",
        f"{s.memory_used:.1f}",
        f"{s.memory_percent:.0f}",
        f"{s.jobs_memory:.1f}",
        "" if s.battery is None else f"{s.battery:.0f}",
        plugged,
        f"{s.disk_free:.0f}",
        str(s.jobs),
        note,
    ]


def tail(folder: Path | None = None, count: int = TAIL_ROWS) -> str:
    """The last `count` rows (from the older file too, if needed), with
    the header.
    """
    folder = folder or LOGS_DIR
    rows: list[str] = []
    for name in ("vitals.1.csv", "vitals.csv"):
        path = folder / name
        if path.exists():
            rows += path.read_text().splitlines()[1:]
    if not rows:
        return (
            f"No vitals yet in {folder}/: the control center writes them "
            "while it's open (make control)."
        )
    return "\n".join([",".join(COLUMNS), *rows[-count:]])
