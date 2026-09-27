"""The machine's vital signs for the control center (roadmap step 6a):
CPU, memory, battery, disk, and how much of it our jobs use. So you know
when to stop before the laptop runs out of breath.
"""

import time
from dataclasses import dataclass
from pathlib import Path

import psutil

REPO = Path(__file__).resolve().parents[2]
GB = 1024**3

# (caution, danger) thresholds: amber, then red.
CPU_LEVELS = (70.0, 85.0)  # % of the whole machine
# macOS keeps most memory in use (caches, compressed memory): about 80 %
# with nothing heavy running here. So memory only warns near the edge.
MEMORY_LEVELS = (88.0, 95.0)  # % in use
BATTERY_LEVELS = (40.0, 20.0)  # % left, only while unplugged
DISK_LEVELS = (20.0, 5.0)  # GB free

NORMAL, CAUTION, DANGER = 0, 1, 2


@dataclass(frozen=True)
class Snapshot:
    cpu: float  # % of the whole machine
    jobs_cpu: float  # our jobs' share of the whole machine, %
    memory_used: float  # GB in use (total minus available)
    memory_total: float  # GB
    jobs_memory: float  # GB our jobs hold
    battery: float | None  # % left, None without a battery
    plugged: bool | None  # on power
    disk_free: float  # GB free where the project lives
    jobs: int  # running

    @property
    def memory_percent(self) -> float:
        return 100 * self.memory_used / self.memory_total

    def levels(self) -> dict[str, int]:
        """How worried to be about each stat."""
        return {
            "cpu": _above(self.cpu, CPU_LEVELS),
            "memory": _above(self.memory_percent, MEMORY_LEVELS),
            "battery": _battery_level(self.battery, self.plugged),
            "disk": _below(self.disk_free, DISK_LEVELS),
        }


def _above(value: float, levels: tuple[float, float]) -> int:
    caution, danger = levels
    if value >= danger:
        return DANGER
    return CAUTION if value >= caution else NORMAL


def _below(value: float, levels: tuple[float, float]) -> int:
    caution, danger = levels
    if value <= danger:
        return DANGER
    return CAUTION if value <= caution else NORMAL


def _battery_level(percent: float | None, plugged: bool | None) -> int:
    if percent is None or plugged:
        return NORMAL
    # Unplugged is worth noticing on its own: training drains it fast.
    return max(_below(percent, BATTERY_LEVELS), CAUTION)


class SystemStats:
    """Samples the machine. Our jobs' share covers each job's process and
    anything it started.
    """

    def __init__(self, every: float = 1.0) -> None:
        self.every = every
        self.cores = psutil.cpu_count() or 1
        self._processes: dict[int, psutil.Process] = {}
        self._last = 0.0
        self.snapshot: Snapshot | None = None
        psutil.cpu_percent(None)  # the first reading starts the clock

    def sample(self, pids: list[int], force: bool = False) -> Snapshot:
        """A fresh snapshot at most every `every` seconds."""
        now = time.monotonic()
        if self.snapshot and not force and now - self._last < self.every:
            return self.snapshot
        self._last = now
        memory = psutil.virtual_memory()
        battery = psutil.sensors_battery()
        jobs_cpu, jobs_memory = self._jobs(pids)
        self.snapshot = Snapshot(
            cpu=psutil.cpu_percent(None),
            jobs_cpu=jobs_cpu / self.cores,
            memory_used=(memory.total - memory.available) / GB,
            memory_total=memory.total / GB,
            jobs_memory=jobs_memory / GB,
            battery=battery.percent if battery else None,
            plugged=battery.power_plugged if battery else None,
            disk_free=psutil.disk_usage(str(REPO)).free / GB,
            jobs=len(pids),
        )
        return self.snapshot

    def _jobs(self, pids: list[int]) -> tuple[float, float]:
        """Our jobs' CPU (% of one core, summed) and memory (bytes)."""
        cpu = memory = 0.0
        seen = set()
        for pid in pids:
            try:
                root = psutil.Process(pid)
                family = [root, *root.children(recursive=True)]
            except psutil.Error:
                continue
            for process in family:
                seen.add(process.pid)
                # One Process object per pid, so its CPU has a baseline.
                tracked = self._processes.setdefault(process.pid, process)
                try:
                    cpu += tracked.cpu_percent(None)
                    memory += tracked.memory_info().rss
                except psutil.Error:
                    continue
        for pid in list(self._processes):
            if pid not in seen:
                del self._processes[pid]
        return cpu, memory
