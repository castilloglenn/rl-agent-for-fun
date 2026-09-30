"""Background jobs: every command runs as its own process (roadmap 6a).

A closed or crashed game window never takes down the control center or a
training run. Stop sends Ctrl+C (SIGINT), so training keeps its exact
resume state. Pause freezes the process in place (SIGSTOP), and resume
continues it (SIGCONT).

A job that writes a run folder names it first ("Run: <folder>"), so the
runs tab knows which run is whose.

Limits (decision 038): at most `max_heavy` heavy jobs at once, and a dead
switch. More than `burst_starts` starts within `burst_seconds` means
something is looping: every job stops, and starts are refused until
`reset`.
"""

import os
import signal
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from src.utils.resources import is_heavy

REPO = Path(__file__).resolve().parents[2]
LOG_LINES = 2000  # kept per job
RUN_LINE = "Run: "  # a run's first line: the folder it writes


class JobRefused(Exception):
    """A start the limits refused. `tripped`: the dead switch did it."""

    def __init__(self, text: str, tripped: bool = False) -> None:
        super().__init__(text)
        self.tripped = tripped


@dataclass(frozen=True)
class JobLimits:
    max_heavy: int = 2  # training, evaluation, imitation at once
    burst_starts: int = 5  # more starts than this within burst_seconds
    burst_seconds: float = 10.0  # ... trip the dead switch


@dataclass
class Job:
    number: int
    label: str  # how you'd type it, for example "make train AGENT=rookie"
    argv: list[str]
    process: subprocess.Popen
    started: float = field(default_factory=time.monotonic)
    ended: float | None = None
    paused: bool = False
    stopped: bool = False  # stopped by you, rather than finished
    log: deque = field(default_factory=lambda: deque(maxlen=LOG_LINES))
    lines_seen: int = 0  # grows with every line, for change detection
    run: str | None = None  # the run folder it writes, once it says
    reader: threading.Thread | None = None  # collects its output

    @property
    def running(self) -> bool:
        return self.process.poll() is None

    @property
    def status(self) -> str:
        if self.running:
            return "paused" if self.paused else "running"
        if self.ended is None:
            self.ended = time.monotonic()
        if self.stopped:
            return "stopped"
        return "done" if self.process.returncode == 0 else "failed"

    @property
    def seconds(self) -> float:
        return (self.ended or time.monotonic()) - self.started


class JobManager:
    def __init__(
        self,
        cwd: Path = REPO,
        on_event: Callable[[str], None] | None = None,
        limits: JobLimits = JobLimits(),
    ) -> None:
        """`on_event(text)` hears each start, stop, pause, resume, and exit
        ("exit #3 code -9"), for the vitals log. Exits come from a thread.
        """
        self.cwd = cwd
        self.jobs: list[Job] = []
        self.on_event = on_event
        self.limits = limits
        self.tripped: str | None = None  # why the dead switch tripped
        self._starts: list[float] = []  # recent start times

    def _event(self, text: str) -> None:
        if self.on_event:
            self.on_event(text)

    def check(self, argv: list[str], now: float | None = None) -> None:
        """Raises JobRefused if the limits refuse this start. A burst of
        starts trips the dead switch: every job stops.
        """
        if self.tripped:
            raise JobRefused(self.tripped, tripped=True)
        now = time.monotonic() if now is None else now
        window = self.limits.burst_seconds
        self._starts = [t for t in self._starts if now - t < window]
        if len(self._starts) >= self.limits.burst_starts:
            self.trip(
                f"{len(self._starts) + 1} jobs started within {window:g} s"
            )
            raise JobRefused(self.tripped, tripped=True)
        if is_heavy(argv):
            heavy = [j for j in self.running if is_heavy(j.argv)]
            if len(heavy) >= self.limits.max_heavy:
                numbers = ", ".join(f"#{j.number}" for j in heavy)
                raise JobRefused(
                    f"{len(heavy)} heavy jobs are running ({numbers}), at "
                    f"most {self.limits.max_heavy}: wait for one, or stop one"
                )
        self._starts.append(now)

    def trip(self, why: str) -> None:
        """The dead switch: stops every job and refuses new ones."""
        self.tripped = why
        self._event(f"dead switch: {why}")
        for job in self.running:
            self.stop(job)  # Ctrl+C: training keeps its resume state

    def reset(self) -> None:
        """Starts are allowed again."""
        if self.tripped:
            self.tripped = None
            self._starts = []
            self._event("dead switch reset")

    def start(self, label: str, argv: list[str]) -> Job:
        """Starts a job, unless the limits refuse it (JobRefused)."""
        self.check(argv)
        # Live output, and plain text (no color codes) for the console.
        env = {
            **os.environ,
            "PYTHONUNBUFFERED": "1",
            "PYTHON_COLORS": "0",
            "NO_COLOR": "1",
        }
        process = subprocess.Popen(
            argv,
            cwd=self.cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        job = Job(len(self.jobs) + 1, label, argv, process)
        self._event(f"start #{job.number} {label}")
        job.reader = threading.Thread(
            target=_read, args=(job, self._event), daemon=True
        )
        job.reader.start()
        self.jobs.append(job)
        return job

    def stop(self, job: Job) -> None:
        """Like Ctrl+C. A second stop, if it's still running, ends it."""
        if not job.running:
            return
        if job.paused:
            self.resume(job)  # a frozen process can't handle Ctrl+C
        # Ctrl+C first. Asked again while it's still running: end it.
        sig = signal.SIGTERM if job.stopped else signal.SIGINT
        job.stopped = True
        job.process.send_signal(sig)
        _add(job, "(stopping)" if sig == signal.SIGINT else "(ending)")
        verb = "stop" if sig == signal.SIGINT else "end"
        self._event(f"{verb} #{job.number}")

    def pause(self, job: Job) -> None:
        if job.running and not job.paused:
            job.process.send_signal(signal.SIGSTOP)
            job.paused = True
            _add(job, "(paused)")
            self._event(f"pause #{job.number}")

    def resume(self, job: Job) -> None:
        if job.running and job.paused:
            job.process.send_signal(signal.SIGCONT)
            job.paused = False
            _add(job, "(resumed)")
            self._event(f"resume #{job.number}")

    def say(self, job: Job, line: str) -> None:
        """A line of our own in the job's console, like "(paused)"."""
        _add(job, line)

    @property
    def running(self) -> list[Job]:
        return [job for job in self.jobs if job.running]

    def stop_all(self, wait: float = 5.0) -> None:
        """Stops every running job, and ends any still running after
        `wait` seconds.
        """
        for job in self.running:
            self.stop(job)
        deadline = time.monotonic() + wait
        while self.running and time.monotonic() < deadline:
            time.sleep(0.05)
        for job in self.running:
            job.process.kill()
        for job in self.jobs:  # so their exits are heard before we go
            if job.reader:
                job.reader.join(timeout=1.0)

    def clear_finished(self) -> None:
        self.jobs = [job for job in self.jobs if job.running]


def _read(job: Job, on_event: Callable[[str], None]) -> None:
    for line in job.process.stdout:
        _add(job, line.rstrip("\n"))
    job.process.wait()
    code = job.process.returncode
    _add(job, f"(exited with code {code})")
    on_event(f"exit #{job.number} code {code}")


def _add(job: Job, line: str) -> None:
    if job.run is None and line.startswith(RUN_LINE):
        job.run = line[len(RUN_LINE) :].strip()
    job.log.append(line)
    job.lines_seen += 1
