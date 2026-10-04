"""The jobs' limits and the dead switch (decision 038). The jobs here are
tiny python commands; nothing trains.
"""

import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402
from absl import flags  # noqa: E402

import src.config  # noqa: E402, F401  (defines the flags)
from src.control.jobs import JobLimits, JobManager, JobRefused  # noqa: E402
from src.control.stats import Snapshot  # noqa: E402
from src.utils.resources import HEAVY, is_heavy  # noqa: E402

SLEEP = [sys.executable, "-c", "import time; time.sleep(30)"]
# A heavy command line that runs nothing heavy: the flag is only a word.
HEAVY_SLEEP = [*SLEEP, "-train", "x"]


def test_heavy_commands_are_real_flags():
    for name in HEAVY:
        assert name in flags.FLAGS
    assert is_heavy(["python", "app.py", "-train", "a", "--trainer", "t"])
    assert is_heavy(["python", "app.py", "-resume_last"])
    assert not is_heavy(["python", "app.py", "-demo", "maze_car"])
    assert not is_heavy(["python", "app.py", "--train_more", "x"])


@pytest.fixture
def manager():
    jobs = JobManager(limits=JobLimits(max_heavy=2, burst_starts=3))
    yield jobs
    jobs.stop_all()


def _wait_stopped(jobs, seconds=5.0):
    deadline = time.monotonic() + seconds
    while jobs.running and time.monotonic() < deadline:
        time.sleep(0.05)
    return not jobs.running


def _wait_stopped_one(job, seconds=5.0):
    deadline = time.monotonic() + seconds
    while job.running and time.monotonic() < deadline:
        time.sleep(0.05)
    return not job.running


def test_at_most_max_heavy_jobs_at_once(manager):
    manager.start("one", HEAVY_SLEEP)
    manager._starts = []  # not a burst: only the heavy limit counts here
    manager.start("two", HEAVY_SLEEP)
    manager._starts = []
    with pytest.raises(JobRefused, match="2 heavy jobs are running") as no:
        manager.start("three", HEAVY_SLEEP)
    assert not no.value.tripped and len(manager.jobs) == 2
    manager.start("light", SLEEP)  # watching, driving: still allowed
    manager.stop(manager.jobs[0])
    assert _wait_stopped_one(manager.jobs[0])
    manager._starts = []
    manager.start("three", HEAVY_SLEEP)  # room again


def test_a_burst_of_starts_trips_the_dead_switch(manager):
    notes = []
    manager.on_event = notes.append
    for i in range(3):
        manager.start(f"job {i}", SLEEP)
    with pytest.raises(JobRefused, match="4 jobs started within 10 s") as no:
        manager.start("one too many", SLEEP)
    assert no.value.tripped and manager.tripped
    assert _wait_stopped(manager)  # every job stopped
    assert all(job.stopped for job in manager.jobs)
    with pytest.raises(JobRefused) as no:  # refused until reset
        manager.start("later", SLEEP)
    assert no.value.tripped
    assert "dead switch: 4 jobs started within 10 s" in notes
    manager.reset()
    assert "dead switch reset" in notes
    manager.start("after the reset", SLEEP)


def test_starts_spread_out_never_trip(manager):
    for i in range(6):
        manager.check(SLEEP, now=100.0 + i * 4)  # one every 4 s
    assert manager.tripped is None


# Memory


def _reading(percent, jobs_gb=0.2):
    return Snapshot(
        cpu=20.0,
        jobs_cpu=10.0,
        memory_used=16.0 * percent / 100,
        memory_total=16.0,
        jobs_memory=jobs_gb,
        battery=None,
        plugged=None,
        disk_free=100.0,
        jobs=1,
    )


def test_no_heavy_job_starts_while_memory_is_red(manager):
    manager.readings = lambda: _reading(97)
    with pytest.raises(JobRefused, match="memory is at 97% .red.") as no:
        manager.start("heavy", HEAVY_SLEEP)
    assert not no.value.tripped and manager.jobs == []
    manager.start("light", SLEEP)  # watching still works
    manager.readings = lambda: _reading(90)  # amber: no room below it
    manager._starts = []
    with pytest.raises(JobRefused, match="needs about 0.7 GB, and 0.0 GB"):
        manager.start("heavy", HEAVY_SLEEP)
    manager.readings = lambda: _reading(80)  # 1.3 GB below amber
    manager.start("heavy", HEAVY_SLEEP)


def test_memory_red_while_our_jobs_fill_it_trips(manager):
    manager.start("job", SLEEP)
    manager.watch_memory(_reading(96, jobs_gb=3.0), now=100.0)
    manager.watch_memory(_reading(96, jobs_gb=3.0), now=104.0)
    assert manager.tripped is None  # not 5 s yet
    manager.watch_memory(_reading(96, jobs_gb=3.0), now=105.0)
    assert manager.tripped == "memory at 96% for 5 s, our jobs hold 3.0 GB"
    assert _wait_stopped(manager)


def test_memory_red_from_other_apps_never_trips(manager):
    for second in range(60):  # our jobs hold only 0.2 GB
        manager.watch_memory(_reading(97), now=float(second))
    assert manager.tripped is None


def test_a_dip_below_red_restarts_the_count(manager):
    manager.watch_memory(_reading(96, jobs_gb=3.0), now=0.0)
    manager.watch_memory(_reading(94, jobs_gb=3.0), now=3.0)  # amber
    manager.watch_memory(_reading(96, jobs_gb=3.0), now=4.0)
    manager.watch_memory(_reading(96, jobs_gb=3.0), now=8.0)
    assert manager.tripped is None
    manager.watch_memory(_reading(96, jobs_gb=3.0), now=9.0)
    assert manager.tripped


# The window


@pytest.fixture
def window():
    from src.control.window import ControlCenter

    center = ControlCenter(limits=JobLimits(max_heavy=1, burst_starts=2))
    # A steady machine, not this one: a training's estimate (with its
    # games' workers) mustn't meet whatever else is open right now.
    center.jobs.readings = lambda: _reading(50)
    yield center
    center.jobs.stop_all()


def test_a_refused_start_says_why(window):
    assert window._start("heavy", HEAVY_SLEEP, False)
    window.jobs._starts = []
    assert window._start("heavy again", HEAVY_SLEEP, False) is None
    text, _ = window.message
    assert text.startswith("Not started: 1 heavy jobs are running (#1)")
    assert window.box is None


def test_the_dead_switch_box_resets_it(window):
    window._start("a", SLEEP, False)
    window._start("b", SLEEP, False)
    assert window._start("c", SLEEP, False) is None
    assert window.box.title == "DEAD SWITCH"
    window.draw()
    window.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
    assert window.box is None and window.jobs.tripped  # still on
    assert window._start("d", SLEEP, False) is None
    assert window.box.title == "DEAD SWITCH"  # it asks again
    window.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
    assert window.jobs.tripped is None
    assert window._start("e", SLEEP, False)


def test_a_memory_trip_opens_the_box(window, monkeypatch):
    monkeypatch.setattr(
        window.jobs,
        "limits",
        JobLimits(max_heavy=1, burst_starts=2, memory_trip_seconds=0),
    )
    monkeypatch.setattr(
        window.stats, "sample", lambda pids, force=False: _reading(96, 2.0)
    )
    window._refresh(force=True)
    assert window.jobs.tripped.startswith("memory at 96%")
    assert window.box.title == "DEAD SWITCH"


def test_a_runaway_loop_trips_instead_of_hanging(window):
    """Decision 038's crash, as any loop that starts again from inside a
    start: the dead switch ends it after `burst_starts` jobs.
    """

    def start():
        job = window._start("runaway", SLEEP, False)
        if job:
            start()  # again, like the chain did
        return job

    start()
    assert len(window.jobs.jobs) == 2 and window.jobs.tripped
    assert window.box.title == "DEAD SWITCH"
    assert _wait_stopped(window.jobs)
