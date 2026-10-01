"""The control center's Runs tab: run status, live curves, charts
(step 6b1). Every run here is written into tmp_path, never runs/.
"""

import json
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from src.control import charts, runs  # noqa: E402
from src.control.charts import Chart, Series  # noqa: E402
from src.control.jobs import JobManager  # noqa: E402
from src.control.runs import CsvTail, RunData, scan  # noqa: E402
from tests.test_control import _wait  # noqa: E402
from tests.test_runner import _run  # noqa: E402
from tests.test_training import _train  # noqa: E402


class _Process:
    def __init__(self, pid=999_999, alive=True):
        self.pid, self.alive = pid, alive

    def poll(self):
        return None if self.alive else 0


def _job(run=None, paused=False, alive=True, pid=999_999):
    from src.control.jobs import Job

    job = Job(1, "a job", [], _Process(pid, alive), paused=paused)
    job.run = run
    return job


def _folder(root, name, kind="training", summary=None, **files):
    """A run folder by hand: its config, and the given files."""
    folder = root / name
    folder.mkdir(parents=True)
    config = {
        "name": name,
        "created_at": "2026-09-27T00:00:00+08:00",
        "driver": {"type": "baseline", "id": "heuristic"},
        "episodes": 10,
        "trainer": {"name": "t", "total_decisions": 1000, "epochs": 10},
        "agent": {"id": "pupil", "start_decisions": 0},
    }
    if kind:
        config["kind"] = kind
    if kind in (None, "episodes"):
        config.pop("agent")
    (folder / "config.json").write_text(json.dumps(config))
    if summary is not None:
        (folder / "summary.json").write_text(json.dumps(summary))
    for file, text in files.items():
        (folder / file.replace("_", ".", 1)).write_text(text)
    return folder


# Reading files that are still being written


def test_a_tail_reads_only_new_complete_lines(tmp_path):
    path = tmp_path / "learning.csv"
    path.write_text("decisions,score_mean\n2048,11.0\n4096,1")
    tail = CsvTail(path)
    assert tail.read()
    assert tail.rows == [{"decisions": 2048.0, "score_mean": 11.0}]
    assert not tail.read()  # the half line waits
    with open(path, "a") as file:
        file.write("2.5\n")
    assert tail.read()
    assert tail.column("score_mean", "decisions") == [
        (2048.0, 11.0),
        (4096.0, 12.5),
    ]


def test_a_rewritten_file_is_read_again(tmp_path):
    path = tmp_path / "learning.csv"
    path.write_text("update,x\n1,1\n2,2\n3,3\n")
    tail = CsvTail(path)
    tail.read()
    path.write_text("update,x\n1,1\n")  # Ctrl+C keeps the last update's
    assert tail.read()
    assert tail.rows == [{"update": 1.0, "x": 1.0}]


def test_a_missing_file_has_no_rows(tmp_path):
    tail = CsvTail(tmp_path / "nothing.csv")
    assert not tail.read() and tail.rows == []


# Status


def test_statuses_from_the_files(tmp_path):
    _folder(tmp_path, "a_done", summary={"interrupted": False})
    stopped = _folder(tmp_path, "b_stopped", summary={"interrupted": True})
    (stopped / "resume.pt").write_bytes(b"")
    _folder(tmp_path, "c_ended")  # no summary, no lock: it crashed
    live = _folder(tmp_path, "d_live")
    (live / "training.lock").write_text(str(os.getpid()))
    _folder(tmp_path, "e_episodes", kind=None, metrics_csv="episode\n0\n")
    rows = {row.name: row for row in scan(tmp_path)}
    assert rows["a_done"].status == runs.DONE
    assert rows["b_stopped"].status == runs.STOPPED
    assert rows["b_stopped"].resumable
    assert rows["c_ended"].status == runs.ENDED
    assert not rows["c_ended"].resumable  # no resume state
    assert rows["d_live"].status == runs.ELSEWHERE  # its lock is alive
    assert rows["e_episodes"].status == runs.ELSEWHERE  # just written
    later = time.time() + runs.LIVE_SECONDS + 1
    rows = {row.name: row for row in scan(tmp_path, now=later)}
    assert rows["e_episodes"].status == runs.ENDED
    assert [row.name for row in scan(tmp_path)][0] == "e_episodes"


def test_our_jobs_are_linked_to_their_runs(tmp_path):
    _folder(tmp_path, "a_run")
    locked = _folder(tmp_path, "b_run")
    (locked / "training.lock").write_text("4242")
    jobs = [_job(run="a_run", paused=True), _job(pid=4242)]
    rows = {row.name: row for row in scan(tmp_path, jobs)}
    assert rows["a_run"].status == runs.PAUSED
    assert rows["a_run"].job is jobs[0]
    assert rows["b_run"].job is jobs[1]  # by the lock's process id
    assert rows["b_run"].status == runs.RUNNING


def test_progress_and_list_lines(tmp_path):
    _folder(
        tmp_path,
        "2026-09-27_003302_train-pupil_seed0",
        learning_csv="decisions,score_mean\n250,1\n",
    )
    (row,) = scan(tmp_path, [_job(run="2026-09-27_003302_train-pupil_seed0")])
    assert row.progress == 0.25
    assert row.line == "09-27 00:33:02 train    pupil         25%"


def test_a_job_learns_its_run_from_its_first_line(tmp_path):
    jobs = JobManager(cwd=tmp_path)
    job = jobs.start(
        "job", [sys.executable, "-c", "print('Run: 2026-09-27_x_seed0')"]
    )
    assert _wait(lambda: not job.running and job.lines_seen >= 2)
    assert job.run == "2026-09-27_x_seed0"


def test_runs_announce_their_folder_first(tmp_path):
    seen = []
    summary = _run(tmp_path, episodes=1, on_start=seen.append)
    assert seen == [summary.folder]
    seen = []
    summary = _train(tmp_path, on_start=seen.append)
    assert seen == [summary.folder]


# One run's details and curves


def test_a_training_run_has_its_curves(tmp_path):
    summary = _train(tmp_path)
    data = RunData(summary.folder, tmp_path / "agents")
    done, total, unit = data.counts()
    assert (done, total, unit) == (512, 512, "decisions")
    chart = data.main_chart()
    training = chart.series[0]
    assert training.label == "training" and len(training.points) == 4
    assert data.options()[0] == "Skills"  # 7d4: the default
    for option in data.options():
        if option in ("Skills", "Driving style"):  # scored ones: below
            continue
        assert data.second_chart(option).series[0].points
    assert "pupil from initial" in data.description()
    assert not data.refresh()  # nothing new


def test_suite_scores_come_from_the_agents_history(tmp_path):
    folder = _folder(
        tmp_path / "runs",
        "r",
        learning_csv="decisions,score_mean,seconds\n100,5,1\n200,9,2\n",
    )
    config = json.loads((folder / "config.json").read_text())
    config["suite"] = {"name": "skills", "version": 1}
    config["stage"] = {"name": "box"}
    (folder / "config.json").write_text(json.dumps(config))
    agent = tmp_path / "agents" / "pupil"
    (agent / "evaluations").mkdir(parents=True)
    events = [
        {"event": "checkpoint_saved", "run": "r", "checkpoint": "a",
         "decisions": 100},
        {"event": "checkpoint_saved", "run": "other", "checkpoint": "b",
         "decisions": 150},
        {"event": "scored", "checkpoint": "a", "suite": "skills-v1",
         "score_mean": 40.0, "share": 1.25, "style_forward": 0.7,
         "style_brake": 0.1, "style_coast": 0.15, "style_reverse": 0.05,
         "skills": {"open_field": 150.0, "braking": 0.4}},
        {"event": "scored", "checkpoint": "b", "suite": "skills-v1",
         "score_mean": 50.0, "share": 2.0},
    ]
    (agent / "history.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n"
    )
    (agent / "evaluations" / "best.json").write_text('{"checkpoint": "a"}')
    baselines = tmp_path / "agents" / "baselines"
    baselines.mkdir()
    (baselines / "skills-v1.json").write_text(json.dumps({"scores": {
        "heuristic": {"skill:open_field": 100.0, "skill:braking": 0.8},
    }}))
    data = RunData(folder, tmp_path / "agents")
    assert data.suite_points == [("a", 100.0, 40.0)]  # only this run's
    assert data.shares == {"a": 1.25}
    assert data.best == ("a", 100.0, 40.0)
    assert data.notes() == "best a: share 1.25"
    # 7d4: each skill's share of the heuristic's.
    assert data.skill_points == {
        "open_field": [(100.0, 1.5)], "braking": [(100.0, 0.5)],
    }
    # 7c9: its driving style over the checkpoints, a line per pedal.
    style = data.second_chart("Driving style")
    assert [s.label for s in style.series] == [
        "forward", "brake", "coast", "reverse",
    ]
    assert style.series[0].points == [(100.0, 0.7)]
    labels = [s.label for s in data.main_chart().series]
    assert labels == ["training", "suite skills-v1", "best a"]
    chart = data.second_chart("Skills")
    assert chart.title == "SKILLS · trained on box"
    labels = [s.label for s in chart.series]
    assert "Open field (trained here)" in labels  # the box: dashed
    assert labels[-3:] == ["average share", "best a", "heuristic"]
    assert chart.series[-2].points == [(100.0, 1.25)]  # the best, by share
    assert data.seconds_left() == pytest.approx(8.0)  # 800 more at 100/s


def test_an_episode_run_has_its_curves(tmp_path):
    summary = _run(tmp_path, episodes=3)
    data = RunData(summary.folder, tmp_path)
    assert data.counts() == (3, 3, "episodes")
    episode, mean = data.main_chart().series
    assert len(episode.points) == 3 and len(mean.points) == 3
    assert data.notes().startswith("best episode")


def test_an_imitation_run_has_its_curves(tmp_path):
    folder = _folder(
        tmp_path,
        "i",
        kind="imitation",
        learning_csv=(
            "epoch,seconds,train_loss,train_accuracy,held_out_loss,"
            "held_out_accuracy,value_loss\n1,0.5,1.7,0.4,1.8,0.35,0.2\n"
        ),
    )
    data = RunData(folder, tmp_path)
    assert data.counts() == (1, 10, "epochs")
    train, held = data.main_chart().series
    assert train.points == [(1.0, 0.4)] and held.points == [(1.0, 0.35)]
    assert [s.label for s in data.second_chart("Loss").series] == [
        "train",
        "held-out",
    ]


def test_rolling_mean():
    points = [(i, float(i)) for i in range(4)]
    assert runs._rolling(points, 2) == [
        (0, 0.0),
        (1, 0.5),
        (2, 1.5),
        (3, 2.5),
    ]


# Charts


def test_ticks_are_round_numbers():
    assert charts.nice_ticks(0, 5347) == [0, 2000, 4000, 6000]
    assert charts.nice_ticks(0.3, 0.7) == [0.3, 0.4, 0.5, 0.6, 0.7]
    flat = charts.nice_ticks(5, 5)
    assert flat[0] < 5 < flat[-1] and len(flat) > 2


def test_number_formats():
    assert charts.compact(2_000_000) == "2M"
    assert charts.compact(1_250_000) == "1.2M"
    assert charts.compact(5347) == "5.3k"
    assert charts.compact(0.02) == "0.02"
    assert charts.readable(4412.4) == "4,412"
    assert charts.readable(2.4617) == "2.46"
    assert charts.percent(0.675) == "68%"


def test_nearest_point():
    series = Series("s", [(0, 1), (10, 2), (20, 3)], (0, 0, 0))
    assert charts.nearest(series, 12) == (10, 2)
    assert charts.nearest(series, 16) == (20, 3)
    assert charts.nearest(Series("e", [], (0, 0, 0)), 5) is None


def test_charts_draw_with_and_without_data():
    pygame.init()
    surface = pygame.Surface((600, 300))
    rect = pygame.Rect(0, 0, 600, 300)
    line = Series("s", [(0, 1.0), (10, 2.0)], (255, 255, 255))
    level = Series("l", [(0, 1.5)], (9, 9, 9), charts.LEVEL)
    chart = Chart("T", [line, level], "{} decisions")
    charts.draw_chart(surface, rect, chart, mouse=(300, 150))
    charts.draw_chart(surface, rect, Chart("T", [], "x {}"))
    assert Chart("T", [level], "x").empty  # a level alone isn't data


def test_a_full_legend_wraps_onto_rows_under_the_header():
    pygame.init()
    surface = pygame.Surface((600, 300))
    rect = pygame.Rect(0, 0, 600, 300)
    many = [
        Series(f"skill number {i}", [(0, 1.0), (1, 2.0)], (9, 9, 9), priority=3)
        for i in range(8)
    ]
    one_row = charts.draw_chart(surface, rect, Chart("T", many, "{}"))
    assert len(one_row.legend) < len(many)  # one row: some dropped
    chart = Chart("T", many, "{}", legend_rows=3)
    rows = charts.draw_chart(surface, rect, chart)
    assert len(rows.legend) == len(many)  # every item, on more rows
    assert len({r.y for r, _ in rows.legend}) > 1
    assert rows.area.y > one_row.area.y  # the plot makes room


# The tab in the window


@pytest.fixture
def window(tmp_path):
    from src.control.window import ControlCenter

    runs_dir = tmp_path / "runs"
    stopped = _folder(runs_dir, "2026-09-27_000000_train-pupil_seed0",
                      summary={"interrupted": True})
    (stopped / "resume.pt").write_bytes(b"")
    center = ControlCenter(runs_dir=runs_dir, agents_dir=tmp_path)
    yield center
    center.jobs.stop_all()


def test_the_runs_tab_opens_and_hides_the_commands(window):
    runs_tab = window.runs_tab
    window.handle(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=1,
            pos=window.tab_rects["Runs"].center,
        )
    )
    assert window.tab == "Runs"
    assert not window.log_box.visible and runs_tab.run_list.visible
    assert runs_tab.selected == "2026-09-27_000000_train-pupil_seed0"
    window.draw()
    window.open_tab("Commands")
    assert window.log_box.visible and not runs_tab.run_list.visible


def test_resume_training_starts_the_resume_action(window, monkeypatch):
    started = []
    monkeypatch.setattr(
        window.jobs,
        "start",
        lambda label, argv: started.append(argv) or _job(),
    )
    window.open_tab("Runs")
    tab = window.runs_tab
    assert tab.buttons["Resume training"].is_enabled
    assert not tab.buttons["Stop"].is_enabled  # not one of our jobs
    tab.press("Resume training")
    assert started[0][-2:] == [
        "-resume",
        "2026-09-27_000000_train-pupil_seed0",
    ]


def test_a_mixed_run_names_its_mix_and_marks_its_maps(tmp_path):
    """7d5a: every map of the mix counts as trained on."""
    folder = _folder(
        tmp_path / "runs",
        "m",
        learning_csv="decisions,score_mean,seconds\n100,5,1\n",
    )
    config = json.loads((folder / "config.json").read_text())
    config["suite"] = {"name": "skills", "version": 1}
    config["stage"] = {"name": "box"}
    config["mix"] = {
        "name": "basics",
        "stages": [{"name": n} for n in ("box", "skill_gaps")],
    }
    (folder / "config.json").write_text(json.dumps(config))
    assert runs.run_stages(config) == ["box", "skill_gaps"]
    assert runs.run_place(config) == "mix basics (2 maps)"
    data = RunData(folder, tmp_path / "agents")
    assert "mix basics (2 maps)" in data.description()
    assert data.main_chart().series[0].label == "training (mixed)"
    labels = [s.label for s in data.second_chart("Skills").series]
    assert "Open field (trained here)" in labels  # on the box
    assert "Threading (trained here)" in labels  # on skill_gaps
    title = data.second_chart("Skills").title
    assert title == "SKILLS · trained on mix basics"


# Runs still starting (7c16)


def _starting_job(argv, number=7):
    job = _job()
    job.number, job.argv, job.label = number, argv, "Train: rookie"
    return job


def test_a_job_without_its_run_yet_gets_a_starting_row(tmp_path):
    train = _starting_job(["python", "app.py", "-train", "rookie"])
    episodes = _starting_job(
        ["python", "app.py", "-run", "h", "--driver", "heuristic"], 8
    )
    other = _starting_job(["python", "app.py", "-eval", "rookie"], 9)
    rows = runs.scan(tmp_path, [train, episodes, other])
    assert sorted((r.name, r.kind, r.who) for r in rows) == [
        ("starting #7", runs.TRAINING, "rookie"),
        ("starting #8", runs.EPISODES, "heuristic"),
    ]  # not the evaluation: it writes no run
    assert all(r.status == runs.STARTING for r in rows)
    assert all("starting" in r.line for r in rows)
    train.run = "2026-10-01_135222_train-rookie_seed0"  # it said its folder
    assert [r.name for r in runs.scan(tmp_path, [train])] == []


def test_a_plan_shows_its_run_starting_from_its_first_step(tmp_path):
    from src.control.chains import Chain
    from src.control.training_plan import Step

    create = _starting_job(["python", "app.py", "-new_agent", "rookie"], 3)
    steps = [
        Step("Create rookie.", "Create an agent", {}),
        Step("Clone the heuristic.", "Clone your driving", {}),
        Step("Train rookie.", "Train", {}),
    ]
    chain = Chain(steps, lambda step, i, n: create, agent="rookie")
    chain.tick()
    (row,) = runs.scan(tmp_path, [create], chains=[chain])
    assert (row.name, row.kind, row.who) == (
        "starting #3",
        runs.IMITATION,  # the first step that makes a run
        "rookie",
    )


def test_the_runs_tab_follows_a_starting_run(window, tmp_path):
    from src.control.chains import Chain
    from src.control.training_plan import Step

    job = _starting_job(["python", "app.py", "-imitate", "rookie"], 5)
    job.log.append("Building the dataset: round 11 of 50")
    chain = Chain(
        [Step("Clone the heuristic.", "Clone your driving", {}),
         Step("Train rookie.", "Train", {})],
        lambda step, i, n: job,
        agent="rookie",
    )
    chain.tick()
    window.chains.append(chain)
    window.open_tab("Runs")
    tab = window.runs_tab
    tab.follow = chain
    tab.refresh(force=True)
    assert tab.selected == "starting #5" and tab.data is None
    assert tab.compare_menu is None  # nothing to compare it with yet
    assert tab.buttons["Stop"].is_enabled  # it can be stopped already
    assert not tab.buttons["Delete run"].is_enabled
    window.draw()  # the spinner, what it's doing, and what's next
    assert runs_tab_doing(job) == "Building the dataset: round 11 of 50"
    # Its run folder appears: the tab moves on to it.
    name = "2026-10-01_135137_imitate-rookie_seed0"
    _folder(tab.runs_dir, name, kind="imitation")
    job.run = name
    tab.refresh(force=True)
    assert tab.selected == name and tab.data is not None


def runs_tab_doing(job):
    from src.control.runs_tab import _doing

    return _doing(job)
