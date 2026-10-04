"""How many games a training plays at once (roadmap 8, decision 073):
as many as the machine has room for, up to the run's most, and fewer
when you need the machine. Checked after every update.

- **Fewer, fast:** memory at amber (88 %), or the whole machine's CPU
  above 85 % for 10 s: one game finishes its round and stops.
- **More, slowly:** memory below 80 % and CPU below 60 % for 60 s, and
  room below amber for one more: one game is added.
- **Never more** than the cores minus the 2 kept free (decision 038),
  minus one for the training process, minus the other heavy jobs. Never
  fewer than 1.

No torch: the readings come from psutil.
"""

import os
import time
from dataclasses import dataclass
from typing import Callable

from src.utils.resources import FREE_CORES

MEMORY_FEWER = 88.0  # % in use: one game fewer at once (the vitals' amber)
MEMORY_MORE = 80.0  # % in use: below it (and calm), one more
CPU_FEWER = 85.0  # % of the whole machine, held FEWER_SECONDS: one fewer
CPU_MORE = 60.0  # % below it (and calm), one more
FEWER_SECONDS = 10.0
MORE_SECONDS = 60.0
DEFAULT_GAMES = 4  # a training's most at once (app.py's --games)
GAME_GB = 0.10  # a game's worker: measured 0.05 GB (8a), doubled
OTHERS_EVERY = 30.0  # s between scans for other heavy jobs (a scan costs)


@dataclass(frozen=True)
class Load:
    memory_percent: float  # in use, of all memory
    memory_total_gb: float
    cpu_percent: float  # the whole machine, since the last reading
    other_heavy: int  # this project's other heavy jobs


def read_load(count_others: bool = True) -> Load:
    """The machine now. Counting other heavy jobs scans every process:
    without it, `other_heavy` is 0.
    """
    import psutil

    memory = psutil.virtual_memory()
    others = 0
    if count_others:
        from src.control.guard import project_processes

        others = sum(
            1
            for p in project_processes()
            if p.heavy and p.pid != os.getpid()
        )
    return Load(
        100 * (memory.total - memory.available) / memory.total,
        memory.total / 2**30,
        psutil.cpu_percent(interval=None),
        others,
    )


class GameCount:
    """Decides the number of games. `read` and `clock` are swappable for
    tests.
    """

    def __init__(
        self,
        most: int,
        read: Callable[[bool], Load] = read_load,
        clock: Callable[[], float] = time.monotonic,
        cores: int | None = None,
    ) -> None:
        self.most = max(most, 1)
        self.read = read
        self.clock = clock
        self.cores = cores or os.cpu_count() or 1
        self.busy_since: float | None = None  # CPU above CPU_FEWER since
        self.calm_since: float | None = None  # room for more since
        self.load: Load | None = None
        self._others_at = float("-inf")
        self._others = 0

    def ceiling(self, load: Load) -> int:
        """The most games now: the run's most, within the free cores."""
        spare = self.cores - FREE_CORES - 1 - load.other_heavy
        return max(min(self.most, spare), 1)

    def first(self) -> int:
        """How many games to start with."""
        load = self._reading()
        room = load.memory_total_gb * (MEMORY_FEWER - load.memory_percent)
        fits = int(room / 100 / GAME_GB)
        now = self.clock()
        self.busy_since, self.calm_since = None, now
        return max(min(self.ceiling(load), fits), 1)

    def check(self, current: int) -> tuple[int, str] | None:
        """A new number of games and why, or None to keep `current`."""
        load = self._reading()
        now = self.clock()
        busy = load.cpu_percent > CPU_FEWER
        if not busy:
            self.busy_since = None
        elif self.busy_since is None:
            self.busy_since = now
        ceiling = self.ceiling(load)
        why = None
        if load.memory_percent >= MEMORY_FEWER:
            why = f"memory {load.memory_percent:.0f}%"
        elif busy and now - self.busy_since >= FEWER_SECONDS:
            why = f"CPU {load.cpu_percent:.0f}% for {FEWER_SECONDS:g} s"
        elif current > ceiling:
            why = f"{load.other_heavy} other heavy jobs"
        if why and current > 1:
            self.busy_since = now if busy else None  # 10 s more for another
            self.calm_since = None
            return current - 1, why
        room = load.memory_total_gb * (MEMORY_FEWER - load.memory_percent)
        calm = (
            load.memory_percent < MEMORY_MORE
            and load.cpu_percent < CPU_MORE
            and room / 100 >= GAME_GB
        )
        if not calm:
            self.calm_since = None
        elif self.calm_since is None:
            self.calm_since = now
        if (
            calm
            and current < ceiling
            and now - self.calm_since >= MORE_SECONDS
        ):
            self.calm_since = now  # another minute for the next one
            return current + 1, (
                f"room: memory {load.memory_percent:.0f}%, "
                f"CPU {load.cpu_percent:.0f}%"
            )
        return None

    def _reading(self) -> Load:
        """A reading, with the other heavy jobs counted at most every
        OTHERS_EVERY seconds.
        """
        now = self.clock()
        count = now - self._others_at >= OTHERS_EVERY
        load = self.read(count)
        if count:
            self._others, self._others_at = load.other_heavy, now
        self.load = Load(
            load.memory_percent,
            load.memory_total_gb,
            load.cpu_percent,
            self._others,
        )
        return self.load


class FixedCount:
    """Always the same number of games (tests, and one game)."""

    def __init__(self, games: int) -> None:
        self.most = max(games, 1)

    def first(self) -> int:
        return self.most

    def check(self, current: int) -> tuple[int, str] | None:
        return None
