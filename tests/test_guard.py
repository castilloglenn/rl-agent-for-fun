"""Every heavy job guards itself (decision 038, fix 5). Nothing here
scans or signals your real jobs: processes are fakes, or ones these tests
start in tmp_path, and the guard's stop and end are replaced.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

from src.control.guard import (
    ACTIONS,
    BASE_GB,
    INPUTS,
    GuardLimits,
    JobGuard,
    ProjectProcess,
    Reading,
    ahead_of,
    estimate_gb,
    model_params,
    project_processes,
    room_for,
    stop_every_job,
)
from src.utils.resources import is_heavy

REPO = Path(__file__).resolve().parents[1]
FINE = Reading(80.0, 0.2, 100.0, 90.0, True)
TRAIN = ["python", "app.py", "-train", "a"]
WATCH = ["python", "app.py", "-demo", "maze_car"]


def _reading(**changes):
    values = {**FINE.__dict__, **changes}
    return Reading(**values)


# At start


def test_the_oldest_heavy_jobs_run_the_rest_dont_start():
    jobs = [
        ProjectProcess(10, 1.0, TRAIN),
        ProjectProcess(11, 2.0, TRAIN),
        ProjectProcess(12, 3.0, TRAIN),
        ProjectProcess(13, 0.5, WATCH),  # watching doesn't count
        ProjectProcess(14, 0.1, ["python", "app.py", "-control"]),
    ]
    assert [p.pid for p in ahead_of(12, jobs, 2)] == [10, 11]
    assert ahead_of(11, jobs, 2) == []  # only one ahead of it
    assert ahead_of(10, jobs, 2) == []
    twins = [ProjectProcess(20, 5.0, TRAIN), ProjectProcess(21, 5.0, TRAIN)]
    assert ahead_of(21, twins, 1) and not ahead_of(20, twins, 1)


def test_it_finds_this_projects_jobs_only(tmp_path):
    code = "import time; time.sleep(30)"
    job = subprocess.Popen(
        [sys.executable, "-c", code, "app.py", "-train", "x"], cwd=tmp_path
    )
    try:
        deadline = time.monotonic() + 5
        found = []
        while not found and time.monotonic() < deadline:
            found = project_processes(tmp_path)
            time.sleep(0.05)
        assert [p.pid for p in found] == [job.pid]
        assert found[0].heavy and not found[0].control
    finally:
        job.kill()


# While it runs


def _guard(parent=100, **limits):
    parents = {"now": parent}
    guard = JobGuard(
        GuardLimits(**limits),
        readings=lambda: FINE,
        parent=lambda: parents["now"],
        stop=lambda: None,
        end=lambda: None,
    )
    return guard, parents


def test_a_healthy_machine_keeps_it_going():
    guard, _ = _guard()
    for second in range(30):
        assert guard.check(FINE, float(second)) is None


def test_it_stops_when_its_parent_ends():
    guard, parents = _guard()
    parents["now"] = 1  # the control center died: launchd adopted it
    assert guard.check(FINE, 0.0) == "the program that started it ended"
    guard, _ = _guard(parent=1)  # orphaned before it even started
    assert guard.check(FINE, 0.0) == "the program that started it ended"


def test_it_stops_on_a_nearly_full_disk():
    guard, _ = _guard()
    why = guard.check(_reading(disk_free=3.2), 0.0)
    assert why == "the disk has 3.2 GB free (red: under 5 GB)"


def test_it_stops_on_a_nearly_empty_battery_unplugged_only():
    guard, _ = _guard()
    assert guard.check(_reading(battery=15.0, plugged=True), 0.0) is None
    why = guard.check(_reading(battery=15.0, plugged=False), 0.0)
    assert why == "the battery is at 15%, unplugged (red: under 20%)"
    assert guard.check(_reading(battery=40.0, plugged=False), 0.0) is None


def test_it_stops_when_this_projects_jobs_fill_memory():
    guard, _ = _guard()
    full = _reading(memory_percent=96.0, jobs_memory=3.0)
    assert guard.check(full, 0.0) is None
    assert guard.check(full, 4.0) is None
    assert "memory at 96% for 5 s" in guard.check(full, 5.0)
    others = _reading(memory_percent=97.0, jobs_memory=0.2)
    guard, _ = _guard()
    for second in range(60):  # other apps fill it: never
        assert guard.check(others, float(second)) is None


def test_the_watcher_stops_the_job_once():
    stops = []
    guard = JobGuard(
        readings=lambda: _reading(disk_free=1.0),
        parent=lambda: 100,
        stop=lambda: stops.append(1),
        end=lambda: stops.append("end"),
        interval=0.01,
        grace=0.05,
    )
    guard.start()
    deadline = time.monotonic() + 5
    while len(stops) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert stops == [1, "end"]  # Ctrl+C, then ended after the grace
    assert "disk" in guard.reason


CHILD = f"""
import sys, time
sys.path.insert(0, {str(REPO)!r})
from src.control.guard import JobGuard, Reading
fine = Reading(80.0, 0.2, 100.0, 90.0, True)
guard = JobGuard(readings=lambda: fine, interval=0.05, grace=30)
guard.start()
open(sys.argv[1] + ".ready", "w").close()
try:
    time.sleep(20)
except KeyboardInterrupt:  # the guard's Ctrl+C
    open(sys.argv[1], "w").write(guard.reason)
"""


def test_an_orphaned_job_stops_itself(tmp_path):
    """Its parent (the control center, here a stand-in) exits at once:
    the job notices within a second and stops like Ctrl+C.
    """
    marker = tmp_path / "stopped.txt"
    child = [sys.executable, "-c", CHILD, str(marker)]
    parent = (
        "import os, subprocess, sys, time\n"
        f"subprocess.Popen({child!r})\n"
        f"while not os.path.exists({str(marker) + '.ready'!r}):\n"
        "    time.sleep(0.02)\n"
    )
    subprocess.run([sys.executable, "-c", parent], check=True)
    deadline = time.monotonic() + 10
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    time.sleep(0.1)
    assert marker.read_text() == "the program that started it ended"


# The manual switch


def test_stop_all_stops_jobs_but_not_the_control_center(tmp_path):
    code = "import time; time.sleep(30)"
    job = subprocess.Popen([sys.executable, "-c", code])
    center = subprocess.Popen([sys.executable, "-c", code])
    try:
        created = psutil.Process(job.pid).create_time()
        processes = [
            ProjectProcess(job.pid, created, TRAIN),
            ProjectProcess(center.pid, 0.0, ["python", "app.py", "-control"]),
        ]
        stopped = stop_every_job(wait=5, processes=processes)
        assert [p.pid for p in stopped] == [job.pid]
        assert job.wait(5) != 0  # Ctrl+C ended it
        assert center.poll() is None  # untouched
    finally:
        job.kill()
        center.kill()


# Fix 6: the machine decides how many (memory estimates)


def _model(folder, hidden):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "model.json").write_text(json.dumps({"hidden": hidden}))


def test_the_parameter_count_matches_the_real_network():
    from src.agents.model import ModelSpec
    from src.agents.network import PolicyNetwork
    from src.drivers.actions import CANONICAL_ACTIONS
    from src.sim.observation import OBSERVATION_NAMES

    assert (INPUTS, ACTIONS) == (
        len(OBSERVATION_NAMES),
        len(CANONICAL_ACTIONS),
    )
    for hidden in ([64, 64], [128, 128], [300, 200, 50]):
        spec = ModelSpec.from_dict(
            {
                "format": 1, "name": "x", "description": "",
                "hidden": hidden, "activation": "tanh",
                "observation_version": 1, "actions": "canonical12",
                "action_repeat": 4,
            }
        )
        network = PolicyNetwork(spec, INPUTS, ACTIONS)
        real = sum(p.numel() for p in network.parameters())
        assert model_params(hidden) == real


def test_the_estimate_reads_each_commands_model(tmp_path):
    _model(tmp_path / "agents" / "big", [4096, 4096])
    _model(tmp_path / "agents" / "tiny", [64, 64])
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "wide.json").write_text('{"hidden": [2048, 2048]}')
    (tmp_path / "models" / "small.json").write_text('{"hidden": [64, 64]}')
    run = tmp_path / "runs" / "2026-09-30_000000_train-big_seed0"
    run.mkdir(parents=True)
    (run / "config.json").write_text(
        '{"kind": "training", "agent": {"id": "big"}}'
    )
    (run / "summary.json").write_text('{"interrupted": true}')
    (run / "resume.pt").write_bytes(b"")

    def gb(*argv):
        return round(estimate_gb(["app.py", *argv], tmp_path), 2)

    assert gb("-train", "big") == 1.56  # 33.7 M parameters
    assert gb("-train", "tiny") == 0.3
    assert gb("-eval", "big") == gb("-train", "big")
    assert gb("-imitate", "new_one", "--model", "wide") == 0.62
    assert gb("-imitate", "new_one") == 0.3  # the default model: small
    assert gb("-resume", run.name) == gb("-train", "big")
    assert gb("-resume_last") == gb("-train", "big")
    assert gb("-run", "r", "--driver", "agent:big@d0100k") == 1.56
    assert gb("-run", "r", "--driver", "heuristic") == BASE_GB
    assert gb("-eval_baselines") == BASE_GB


def test_room_for_a_job_below_amber_and_under_the_cap(tmp_path):
    _model(tmp_path / "agents" / "big", [4096, 4096])
    train = ["app.py", "-train", "big"]
    limits = GuardLimits(max_heavy=8)
    # 16 GB: amber at 14.08 GB. It needs 1.56 GB.
    assert room_for(train, 12.0, 16.0, 0, limits, tmp_path) is None
    why = room_for(train, 13.2, 16.0, 0, limits, tmp_path)
    assert why.startswith("it needs about 1.6 GB, and 0.9 GB is free")
    why = room_for(train, 1.0, 16.0, 8, limits, tmp_path)
    assert why.startswith("8 heavy jobs are running, at most 8")


def test_by_default_the_cap_is_the_cores_minus_two():
    cores = os.cpu_count() or 1
    assert GuardLimits().heavy_cap == max(cores - 2, 1)
    assert GuardLimits(max_heavy=3).heavy_cap == 3


def test_a_job_far_over_its_estimate_is_stopped():
    guard, _ = _guard()
    guard.expected_gb = 0.3  # a small training: its limit is 1.1 GB
    assert guard.check(_reading(own_memory=0.9), 0.0) is None
    why = guard.check(_reading(own_memory=4.2), 0.0)
    assert why == (
        "it holds 4.2 GB, far more than its estimate (0.3 GB, limit 1.1 GB)"
    )


def test_runs_count_as_heavy():
    assert is_heavy(["app.py", "-run", "r", "--driver", "heuristic"])
    assert not is_heavy(["app.py", "-run_best", "r"])  # a replay window
