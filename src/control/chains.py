"""Chains of jobs (roadmap step 6b2): commands run one after another, each
starting only when the one before it succeeded. The Training tab's plans
run this way (create, then imitate, then train), so they need no command
of their own: in a terminal it's `... && ...`.

Stopping a step, or a step failing, cancels the rest.

Starting a step can tick the chain again from inside (the window
refreshes, and the refresh ticks every chain), before the new job is
recorded. Those ticks are ignored, so each step starts once.
"""

from dataclasses import dataclass, field
from typing import Callable

from src.control.jobs import Job

WAITING, RUNNING, DONE, CANCELLED, FAILED = (
    "waiting",
    "running",
    "done",
    "cancelled",
    "failed",
)


@dataclass
class Chain:
    steps: list  # anything `start` understands, in order
    start: Callable[[object, int, int], Job | None]  # (step, i, n) -> job
    say: Callable[[Job, str], None] = lambda job, line: None
    agent: str = ""  # what it works on, so nothing else trains it meanwhile
    jobs: list[Job] = field(default_factory=list)
    state: str = WAITING
    starting: bool = False  # inside `start`: ticks meanwhile are ignored

    @property
    def job(self) -> Job | None:
        """The current (or last) step's job."""
        return self.jobs[-1] if self.jobs else None

    @property
    def run(self) -> str | None:
        """The newest run folder any step wrote."""
        return next((j.run for j in reversed(self.jobs) if j.run), None)

    @property
    def active(self) -> bool:
        return self.state in (WAITING, RUNNING)

    def tick(self) -> None:
        """Starts the first step, or the next one once the current one
        succeeded. Call it often.
        """
        if not self.active or self.starting:
            return
        job = self.job
        if job is None:
            self._next()
            return
        if job.running:
            return
        if job.stopped or job.process.returncode != 0:
            self.state = CANCELLED if job.stopped else FAILED
            left = len(self.steps) - len(self.jobs)
            if left:
                why = "stopped" if job.stopped else "failed"
                self.say(
                    job,
                    f"(this step {why}: the chain's other {left} step"
                    f"{'s' if left > 1 else ''} won't run)",
                )
            return
        if len(self.jobs) == len(self.steps):
            self.state = DONE
            return
        self._next()

    def _next(self) -> None:
        i = len(self.jobs)
        self.starting = True
        try:
            job = self.start(self.steps[i], i, len(self.steps))
        finally:
            self.starting = False
        if job is None:  # it couldn't start (a field was missing)
            self.state = FAILED
            return
        self.jobs.append(job)
        self.state = RUNNING
