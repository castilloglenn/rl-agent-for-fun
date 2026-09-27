"""The vitals log: the machine's readings, kept small (step 6b1)."""

import csv
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from src.control.jobs import JobManager  # noqa: E402
from src.control.stats import Snapshot  # noqa: E402
from src.control.vitals import COLUMNS, VitalsLog, row, tail  # noqa: E402
from tests.test_control import _wait  # noqa: E402


def _snap(cpu=20.0, battery=80.0, plugged=True):
    return Snapshot(
        cpu=cpu,
        jobs_cpu=10.4,
        memory_used=13.24,
        memory_total=16.0,
        jobs_memory=0.43,
        battery=battery,
        plugged=plugged,
        disk_free=119.4,
        jobs=2,
    )


def _rows(path):
    with open(path) as file:
        return list(csv.DictReader(file))


def test_a_row_every_ten_seconds(tmp_path):
    log = VitalsLog(tmp_path)
    assert log.record(_snap(), 0.0)
    assert not log.record(_snap(), 5.0)
    assert log.record(_snap(), 10.0)
    rows = _rows(tmp_path / "vitals.csv")
    assert len(rows) == 2 and list(rows[0]) == list(COLUMNS)
    assert rows[0]["cpu"] == "20" and rows[0]["mem"] == "83"
    assert rows[0]["mem_gb"] == "13.2" and rows[0]["plugged"] == "1"


def test_a_level_change_is_written_at_once(tmp_path):
    log = VitalsLog(tmp_path)
    log.record(_snap(cpu=20), 0.0)
    assert log.record(_snap(cpu=90), 1.0)  # red: no waiting
    assert not log.record(_snap(cpu=91), 2.0)  # still red
    rows = _rows(tmp_path / "vitals.csv")
    assert rows[-1]["note"] == "level change" and rows[-1]["cpu"] == "90"


def test_notes_carry_the_latest_readings(tmp_path):
    log = VitalsLog(tmp_path)
    log.note("open")  # before any reading
    log.record(_snap(), 0.0)
    log.note("exit #3 code -9")
    first, _, last = _rows(tmp_path / "vitals.csv")
    assert first["note"] == "open" and first["cpu"] == ""
    assert last["note"] == "exit #3 code -9" and last["cpu"] == "20"


def test_no_battery(tmp_path):
    values = dict(zip(COLUMNS, row(_snap(battery=None, plugged=None))))
    assert values["battery"] == "" and values["plugged"] == ""


def test_the_file_stays_small(tmp_path):
    log = VitalsLog(tmp_path, every=0, max_bytes=2_000)
    for i in range(200):
        log.record(_snap(), float(i))
    current = tmp_path / "vitals.csv"
    older = tmp_path / "vitals.1.csv"
    assert current.stat().st_size <= 2_100  # one row over, at most
    assert older.stat().st_size <= 2_100
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["vitals.1.csv", "vitals.csv"]  # never a third file
    assert _rows(current) and _rows(older)  # each keeps its header


def test_tail_reads_across_both_files(tmp_path):
    log = VitalsLog(tmp_path, every=0, max_bytes=800)
    for i in range(20):
        log.note(f"n{i}", _snap())
    lines = tail(tmp_path, count=12).splitlines()
    assert lines[0] == ",".join(COLUMNS)
    assert len(lines) == 13 and lines[-1].endswith(",n19")


def test_tail_without_a_log(tmp_path):
    assert tail(tmp_path).startswith("No vitals yet")


def test_jobs_report_their_starts_and_exits(tmp_path):
    heard = []
    jobs = JobManager(cwd=tmp_path, on_event=heard.append)
    job = jobs.start(
        "sleepy", [sys.executable, "-c", "import time; time.sleep(30)"]
    )
    jobs.pause(job)
    jobs.resume(job)
    jobs.stop(job)
    assert _wait(lambda: any(h.startswith("exit #1") for h in heard))
    assert heard[:4] == ["start #1 sleepy", "pause #1", "resume #1", "stop #1"]


def test_the_control_center_logs_open_and_quit(tmp_path):
    from src.control.window import ControlCenter

    center = ControlCenter(logs_dir=tmp_path)
    center._refresh(force=True)
    center.quit()
    notes = [r["note"] for r in _rows(tmp_path / "vitals.csv")]
    assert notes[0] == "open" and notes[-1] == "quit"


def test_no_log_by_default():
    from src.control.window import ControlCenter

    center = ControlCenter()
    assert center.vitals is None  # tests never write into logs/
    center.jobs.stop_all()
