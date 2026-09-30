"""Every heavy job guards itself (decision 038, fix 5), started from the
control center or a terminal, so the last safety gate needs nothing else
running:

- **At start:** if `max_heavy` heavy jobs of this project already run, it
  doesn't start. The oldest ones run, so even a burst of starts ends with
  `max_heavy` jobs.
- **While it runs,** a watcher thread checks every second, and stops the
  job like Ctrl+C (a training keeps its resume state) when the program that
  started it ended (the control center closed or crashed), the disk is
  nearly full, the battery is nearly empty and unplugged, or memory stays
  red while this project's heavy jobs fill it.

`stop_every_job` is the manual switch (`make stop_all`).
"""

import os
import signal
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import psutil

from src.control.stats import BATTERY_LEVELS, DISK_LEVELS, GB, MEMORY_LEVELS
from src.utils.resources import is_heavy

REPO = Path(__file__).resolve().parents[2]
MEMORY_RED = MEMORY_LEVELS[1]  # % in use
DISK_RED = DISK_LEVELS[1]  # GB free
BATTERY_RED = BATTERY_LEVELS[1]  # % left, unplugged
STOP_GRACE = 60.0  # s after its Ctrl+C before the guard ends it
ORPHANED = 1  # the parent of a process whose parent ended (launchd)


@dataclass(frozen=True)
class GuardLimits:
    max_heavy: int = 2
    memory_trip_gb: float = 1.0
    memory_trip_seconds: float = 5.0


@dataclass(frozen=True)
class ProjectProcess:
    """A process running this project's app.py."""

    pid: int
    created: float
    argv: list[str] = field(default_factory=list)
    memory: float = 0.0  # GB

    @property
    def heavy(self) -> bool:
        return is_heavy(self.argv)

    @property
    def control(self) -> bool:
        return "-control" in self.argv


@dataclass(frozen=True)
class Reading:
    memory_percent: float
    jobs_memory: float  # GB this project's heavy jobs hold
    disk_free: float  # GB
    battery: float | None  # % left
    plugged: bool | None


def project_processes(repo: Path = REPO) -> list[ProjectProcess]:
    """Every process running app.py in `repo`."""
    found = []
    attrs = ["pid", "cmdline", "create_time", "memory_info"]
    for process in psutil.process_iter(attrs):
        argv = process.info["cmdline"] or []
        if not any(Path(arg).name == "app.py" for arg in argv):
            continue
        try:
            if Path(process.cwd()).resolve() != repo:
                continue
        except psutil.Error:
            continue
        memory = process.info["memory_info"]
        found.append(
            ProjectProcess(
                process.info["pid"],
                process.info["create_time"],
                argv,
                memory.rss / GB if memory else 0.0,
            )
        )
    return found


def ahead_of(
    pid: int, processes: list[ProjectProcess], max_heavy: int
) -> list[ProjectProcess]:
    """The heavy jobs started before `pid`, if `max_heavy` of them (or
    more) run: then it mustn't start. Empty if it may.
    """
    me = next((p for p in processes if p.pid == pid), None)
    mine = (me.created, pid) if me else (float("inf"), pid)
    earlier = [
        p
        for p in processes
        if p.pid != pid and p.heavy and (p.created, p.pid) < mine
    ]
    return earlier if len(earlier) >= max_heavy else []


def read_machine(repo: Path = REPO) -> Reading:
    memory = psutil.virtual_memory()
    percent = 100 * (memory.total - memory.available) / memory.total
    jobs = 0.0
    if percent >= MEMORY_RED:  # only then: scanning processes costs
        jobs = sum(p.memory for p in project_processes(repo) if p.heavy)
    battery = psutil.sensors_battery()
    return Reading(
        memory_percent=percent,
        jobs_memory=jobs,
        disk_free=psutil.disk_usage(str(repo)).free / GB,
        battery=battery.percent if battery else None,
        plugged=battery.power_plugged if battery else None,
    )


def _interrupt_self() -> None:
    os.kill(os.getpid(), signal.SIGINT)  # Ctrl+C, in the main thread


def _end_self() -> None:
    os.kill(os.getpid(), signal.SIGTERM)


class JobGuard:
    """Watches this job's machine and its parent. `readings`, `parent`
    (a function returning the parent's pid), `stop`, and `end` are for
    tests.
    """

    def __init__(
        self,
        limits: GuardLimits = GuardLimits(),
        readings: Callable[[], Reading] = read_machine,
        parent: Callable[[], int] = os.getppid,
        stop: Callable[[], None] = _interrupt_self,
        end: Callable[[], None] = _end_self,
        interval: float = 1.0,
        grace: float = STOP_GRACE,
    ) -> None:
        self.limits = limits
        self.readings = readings
        self.parent = parent
        self.started_by = parent()
        self.stop = stop
        self.end = end
        self.interval = interval
        self.grace = grace
        self.reason: str | None = None
        self._red_since: float | None = None

    def check(self, reading: Reading, now: float) -> str | None:
        """Why the job must stop now, or None."""
        parent = self.parent()
        if parent != self.started_by or parent == ORPHANED:
            return "the program that started it ended"
        if reading.disk_free < DISK_RED:
            return (
                f"the disk has {reading.disk_free:.1f} GB free "
                f"(red: under {DISK_RED:g} GB)"
            )
        battery = reading.battery
        if reading.plugged is False and battery is not None:
            if battery < BATTERY_RED:
                return (
                    f"the battery is at {battery:.0f}%, unplugged "
                    f"(red: under {BATTERY_RED:g}%)"
                )
        limits = self.limits
        if (
            reading.memory_percent >= MEMORY_RED
            and reading.jobs_memory >= limits.memory_trip_gb
        ):
            if self._red_since is None:
                self._red_since = now
            if now - self._red_since >= limits.memory_trip_seconds:
                return (
                    f"memory at {reading.memory_percent:.0f}% for "
                    f"{limits.memory_trip_seconds:g} s, this project's "
                    f"heavy jobs hold {reading.jobs_memory:.1f} GB"
                )
        else:
            self._red_since = None
        return None

    def start(self) -> None:
        threading.Thread(target=self._watch, daemon=True).start()

    def _watch(self) -> None:
        while True:
            reason = self.check(self.readings(), time.monotonic())
            if reason:
                break
            time.sleep(self.interval)
        self.reason = reason
        print(
            f"Guard: stopping, {reason}. A training keeps its resume "
            "state: make resume_last",
            flush=True,
        )
        self.stop()
        time.sleep(self.grace)  # still here: Ctrl+C didn't end it
        print("Guard: ending it", flush=True)
        self.end()


def stop_every_job(
    repo: Path = REPO,
    wait: float = 10.0,
    processes: list[ProjectProcess] | None = None,
) -> list[ProjectProcess]:
    """Stops every app.py job of this project but the control center (and
    this one): Ctrl+C, then ends any still running after `wait` seconds.
    Returns the jobs it stopped. `processes`: the ones to consider (tests),
    else every one in `repo`.
    """
    if processes is None:
        processes = project_processes(repo)
    me = os.getpid()
    targets = [p for p in processes if p.pid != me and not p.control]
    for target in targets:
        _signal(target.pid, signal.SIGCONT)  # a paused job can't Ctrl+C
        _signal(target.pid, signal.SIGINT)
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline and any(_alive(t) for t in targets):
        time.sleep(0.1)
    for target in targets:
        if _alive(target):
            _signal(target.pid, signal.SIGTERM)
    return targets


def _signal(pid: int, sig: int) -> None:
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        pass


def _alive(target: ProjectProcess) -> bool:
    try:
        process = psutil.Process(target.pid)
        return (
            process.create_time() == target.created
            and process.status() != psutil.STATUS_ZOMBIE
        )
    except psutil.Error:
        return False
