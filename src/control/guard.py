"""Every heavy job guards itself (decision 038, fix 5), started from the
control center or a terminal, so the last safety gate needs nothing else
running:

- **At start (fix 6: the machine decides how many):** it starts only if
  there's room: its estimated memory (`estimate_gb`, from its model's size)
  fits below amber, and fewer heavy jobs of this project run than the cores
  minus the ones kept free. The oldest ones run, so even a burst of starts
  ends within the limit.
- **While it runs,** a watcher thread checks every second, and stops the
  job like Ctrl+C (a training keeps its resume state) when the program that
  started it ended (the control center closed or crashed), the disk is
  nearly full, the battery is nearly empty and unplugged, it holds far more
  memory than its estimate, or memory stays red while this project's heavy
  jobs fill it.

`stop_every_job` is the manual switch (`make stop_all`).
"""

import os
import signal
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import json

import psutil

from src.control.stats import BATTERY_LEVELS, DISK_LEVELS, GB, MEMORY_LEVELS
from src.utils import named_files
from src.utils.resources import FREE_CORES, is_heavy

REPO = Path(__file__).resolve().parents[2]
MEMORY_AMBER, MEMORY_RED = MEMORY_LEVELS  # % in use
DISK_RED = DISK_LEVELS[1]  # GB free
BATTERY_RED = BATTERY_LEVELS[1]  # % left, unplugged
STOP_GRACE = 60.0  # s after its Ctrl+C before the guard ends it
ORPHANED = 1  # the parent of a process whose parent ended (launchd)
# Memory a heavy job needs, measured on 2026-09-30 (a process with the env,
# torch, a model, Adam steps, and a checkpoint saved and loaded): 0.31 GB
# for 64x64 and 128x128, 0.62 GB for 2048x2048, 1.41 GB for 4096x4096.
BASE_GB = 0.30  # the process, with a small model
BYTES_PER_PARAM = 40  # measured 33 to 38: weights, gradients, Adam, a save
INPUTS, ACTIONS = 15, 12  # observation layout 1, canonical12 (tested)
DEFAULT_MODEL = "small"  # app.py's --model default


@dataclass(frozen=True)
class GuardLimits:
    max_heavy: int = 0  # 0: the cores minus FREE_CORES
    memory_trip_gb: float = 1.0
    memory_trip_seconds: float = 5.0

    @property
    def heavy_cap(self) -> int:
        cores = os.cpu_count() or 1
        return self.max_heavy or max(cores - FREE_CORES, 1)


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
    own_memory: float = 0.0  # GB this job holds


# Memory estimates


def model_params(hidden: list[int]) -> int:
    """The policy and value networks' parameters (src/agents/network.py:
    two separate MLPs over the same hidden sizes)."""

    def mlp(sizes: list[int]) -> int:
        return sum((a + 1) * b for a, b in zip(sizes, sizes[1:]))

    return mlp([INPUTS, *hidden, ACTIONS]) + mlp([INPUTS, *hidden, 1])


def estimate_gb(argv: list[str], repo: Path = REPO) -> float:
    """About how much memory a heavy command line needs."""
    hidden = _hidden(argv, repo)
    params = model_params(hidden) if hidden else 0
    return BASE_GB + params * BYTES_PER_PARAM / GB


def _after(argv: list[str], flag: str) -> str | None:
    if flag in argv and argv.index(flag) + 1 < len(argv):
        return argv[argv.index(flag) + 1]
    return None


def _hidden(argv: list[str], repo: Path) -> list[int] | None:
    agent = _agent(argv, repo)
    model = repo / "agents" / agent / "model.json" if agent else None
    if not (model and model.exists()):  # a new agent (imitate): --model
        name = _after(argv, "--model") or DEFAULT_MODEL
        model = named_files.path_of("models", name, repo)
    return _read(model).get("hidden")


def _agent(argv: list[str], repo: Path) -> str | None:
    for flag in ("-train", "-eval", "-imitate"):
        if _after(argv, flag):
            return _after(argv, flag)
    driver = _after(argv, "--driver") or ""
    if driver.startswith("agent:"):
        return driver[len("agent:"):].split("@")[0]
    run = _after(argv, "-resume")
    folder = repo / "runs" / run if run else None
    if "-resume_last" in argv:
        folder = _last_stopped_run(repo / "runs")
    if folder:
        return (_read(folder / "config.json").get("agent") or {}).get("id")
    return None


def _last_stopped_run(runs: Path) -> Path | None:
    """Like src/experiments/training.last_stopped_run, without torch."""
    for folder in sorted(runs.glob("*/"), reverse=True):
        config = _read(folder / "config.json")
        summary = _read(folder / "summary.json")
        if (
            config.get("kind") == "training"
            and summary.get("interrupted")
            and (folder / "resume.pt").exists()
        ):
            return folder
    return None


def _read(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def room_for(
    argv: list[str],
    used_gb: float,
    total_gb: float,
    heavy_running: int,
    limits: GuardLimits = GuardLimits(),
    repo: Path = REPO,
) -> str | None:
    """Why there's no room for this heavy job now, or None: fewer heavy
    jobs than the cap, and its estimate fits while memory stays below
    amber.
    """
    cap = limits.heavy_cap
    if heavy_running >= cap:
        return (
            f"{heavy_running} heavy jobs are running, at most {cap} "
            f"({os.cpu_count()} cores, {FREE_CORES} kept free)"
        )
    need = estimate_gb(argv, repo)
    room = total_gb * MEMORY_AMBER / 100 - used_gb
    if need > room:
        return (
            f"it needs about {need:.1f} GB, and {max(room, 0):.1f} GB is "
            f"free below amber ({MEMORY_AMBER:g}%): close some apps, stop "
            "a job, or pick a smaller model"
        )
    return None


def job_limit_gb(expected: float) -> float:
    """More than this and its estimate was badly wrong: stop it."""
    return 2 * expected + 0.5


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
        own_memory=psutil.Process().memory_info().rss / GB,
    )


def start_problem(
    argv: list[str], limits: GuardLimits = GuardLimits(), repo: Path = REPO
) -> str | None:
    """Why this heavy job (this process) mustn't start, or None. The
    oldest jobs go first, so a burst of starts ends within the cap.
    """
    processes = project_processes(repo)
    ahead = ahead_of(os.getpid(), processes, limits.heavy_cap)
    if ahead:
        pids = ", ".join(str(p.pid) for p in ahead)
        return (
            f"{len(ahead)} heavy jobs of this project are running (pids "
            f"{pids}), at most {limits.heavy_cap}. Wait for one, or stop "
            "them all: make stop_all"
        )
    reading = read_machine(repo)
    if reading.memory_percent >= MEMORY_RED:
        return f"memory is at {reading.memory_percent:.0f}% (red)"
    memory = psutil.virtual_memory()
    used = (memory.total - memory.available) / GB - reading.own_memory
    why = room_for(argv, used, memory.total / GB, 0, limits, repo)
    if why:
        return why
    return JobGuard(limits).check(reading, time.monotonic())


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
        expected_gb: float = BASE_GB,
    ) -> None:
        """`expected_gb`: its memory estimate (the per-job cap)."""
        self.limits = limits
        self.expected_gb = expected_gb
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
        limit = job_limit_gb(self.expected_gb)
        if reading.own_memory > limit:
            return (
                f"it holds {reading.own_memory:.1f} GB, far more than its "
                f"estimate ({self.expected_gb:.1f} GB, limit {limit:.1f} GB)"
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
