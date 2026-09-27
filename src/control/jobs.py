"""Background jobs: every command runs as its own process (roadmap 6a).

A closed or crashed game window never takes down the control center or a
training run. Stop sends Ctrl+C (SIGINT), so training keeps its exact
resume state. Pause freezes the process in place (SIGSTOP), and resume
continues it (SIGCONT).

A job that writes a run folder names it first ("Run: <folder>"), so the
runs tab knows which run is whose.
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

REPO = Path(__file__).resolve().parents[2]
LOG_LINES = 2000  # kept per job
RUN_LINE = "Run: "  # a run's first line: the folder it writes


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
    ) -> None:
        """`on_event(text)` hears each start, stop, pause, resume, and exit
        ("exit #3 code -9"), for the vitals log. Exits come from a thread.
        """
        self.cwd = cwd
        self.jobs: list[Job] = []
        self.on_event = on_event

    def _event(self, text: str) -> None:
        if self.on_event:
            self.on_event(text)

    def start(self, label: str, argv: list[str]) -> Job:
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
