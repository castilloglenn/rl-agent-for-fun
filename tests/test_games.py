"""Several games at once (roadmap 8, decision 073): workers, the rollout
split over the games, their number following the machine, and nothing
left running.
"""

import csv
import json
import time

import psutil
import pytest

from src.agents.model import load_model_spec
from src.agents.store import create_agent
from src.config import get_maze_car_config
from src.experiments import game_count
from src.experiments.game_count import GameCount, Load
from src.experiments.games import GameSetup, WorkerGame
from src.experiments.training import resume_training, train_agent
from src.replay.format import read_replay
from src.replay.replayer import Replayer
from tests.test_training import SHORT, TINY


def _train(where, stage="basics", **kwargs):
    root = where / "agents"
    if not (root / "pupil").exists():
        create_agent("pupil", load_model_spec("small"), root=root)
    config = get_maze_car_config()
    config.stage = stage
    return train_agent(
        "pupil", TINY, config, rules=SHORT, runs_dir=where / "runs",
        agents_root=root, **kwargs,
    )


def _rows(path, drop=()):
    with open(path) as file:
        return [
            {k: v for k, v in row.items() if k not in drop}
            for row in csv.DictReader(file)
        ]


def _workers() -> list:
    return [
        p for p in psutil.Process().children(recursive=True)
        if "src.experiments.game_worker" in " ".join(p.cmdline())
    ]


# Training with several games


def test_one_game_in_a_worker_is_the_same_run(tmp_path):
    local = _train(tmp_path / "local")
    worker = _train(tmp_path / "worker", workers=True)
    for name, drop in (("learning.csv", {"seconds"}), ("metrics.csv", ())):
        assert _rows(local.folder / name, drop) == _rows(
            worker.folder / name, drop
        )


def test_games_split_the_rollout_and_repeat(tmp_path):
    first = _train(tmp_path / "a", games=2)
    second = _train(tmp_path / "b", games=2)
    learning = _rows(first.folder / "learning.csv")
    assert [int(r["decisions"]) for r in learning] == [128, 256, 384, 512]
    assert {r["games"] for r in learning} == {"2"}
    metrics = _rows(first.folder / "metrics.csv")
    assert {r["game"] for r in metrics} == {"1", "2"}
    assert sorted(int(r["seed"]) for r in metrics) == list(range(len(metrics)))
    assert {r["stage"] for r in metrics} == {
        "box", "pillars", "s_curve", "arena",
    }  # four maps over two games: the one furthest behind each time
    for name in ("learning.csv", "metrics.csv"):
        drop = {"seconds"}
        assert _rows(first.folder / name, drop) == _rows(
            second.folder / name, drop
        )  # the same seed and games: the same run
    config = json.loads((first.folder / "config.json").read_text())
    assert config["games"] == 2
    assert not _workers()  # all ended with the training


def test_replays_saved_by_workers_verify(tmp_path):
    summary = _train(tmp_path, games=2)
    replays = sorted((summary.folder / "replays").glob("*.jsonl.gz"))
    assert replays
    for path in replays:
        assert Replayer(read_replay(path)).run().ok, path.name


class Steps:
    """A count that changes on cue: (update number, games)."""

    def __init__(self, first, changes):
        self.most, self.first_games = 2, first
        self.changes = dict(changes)
        self.calls = 0

    def first(self):
        return self.first_games

    def check(self, current):
        self.calls += 1
        games = self.changes.get(self.calls)
        return None if games is None else (games, "test")


def test_a_game_leaving_finishes_its_round(tmp_path):
    summary = _train(tmp_path, games=2, count=Steps(2, {1: 1}))
    learning = _rows(summary.folder / "learning.csv")
    assert learning[0]["games"] == "2" and learning[-1]["games"] == "1"
    metrics = _rows(summary.folder / "metrics.csv")
    leaving = [r for r in metrics if r["game"] == "2"]
    assert leaving and all(
        r["ended_by"] in ("time", "wrecked") for r in leaving
    )  # every round of the game that left was played to its end
    assert int(learning[-1]["decisions"]) == 512
    assert not _workers()


def test_a_game_joins_when_theres_room(tmp_path):
    summary = _train(tmp_path, games=2, count=Steps(1, {1: 2}))
    learning = _rows(summary.folder / "learning.csv")
    assert [r["games"] for r in learning] == ["1", "2", "2", "2"]
    assert {r["game"] for r in _rows(summary.folder / "metrics.csv")} >= {
        "2"
    }


def test_a_run_with_games_resumes(tmp_path):
    from tests.test_resume import _stop_at

    stopped = _train(tmp_path, games=2, on_update=_stop_at(2))
    assert stopped.interrupted and not _workers()
    resumed = resume_training(stopped.folder, agents_root=tmp_path / "agents")
    assert resumed.decisions == 512
    learning = _rows(resumed.folder / "learning.csv")
    assert {r["games"] for r in learning} == {"2"}  # the run's own most


def test_a_worker_ends_when_its_training_does():
    """Its pipe is its lifeline: closed (the training ended, even
    killed), the worker ends.
    """
    from src.envs.maze_car.rewards import load_reward_profile
    from src.sim.rules import load_rules
    from src.sim.stage import load_stage

    config = get_maze_car_config()
    config.show_gui = False
    setup = GameSetup(
        config, "test", load_reward_profile("default").to_dict(),
        load_rules("standard").to_dict(), (load_stage("box").to_dict(),), 4,
    )
    game = WorkerGame(setup)
    game.send(("start", 0, "box", {}, None))
    assert len(game.receive()) > 0
    game.process.stdin.close()  # as when the training process dies
    assert game.process.wait(timeout=10) == 0


# How many games


class Machine:
    def __init__(self, memory=50.0, cpu=10.0, others=0):
        self.memory, self.cpu, self.others = memory, cpu, others
        self.now = 0.0

    def read(self, count_others=True):
        return Load(self.memory, 16.0, self.cpu, self.others)

    def clock(self):
        return self.now


def _count(machine, most=4, cores=10):
    return GameCount(most, machine.read, machine.clock, cores=cores)


def test_it_starts_with_what_fits():
    machine = Machine()
    assert _count(machine).first() == 4  # the most
    assert _count(machine, most=12).first() == 7  # 10 cores - 2 - 1
    machine.memory = 87.0  # 1 % of 16 GB below amber: about 1 game
    assert _count(machine).first() == 1
    machine.memory = 95.0
    assert _count(machine).first() == 1  # never fewer than one


def test_memory_at_amber_drops_a_game_at_once():
    machine = Machine()
    count = _count(machine)
    count.first()
    machine.memory = game_count.MEMORY_FEWER
    assert count.check(4) == (3, "memory 88%")
    assert count.check(1) is None  # never fewer than one


def test_a_busy_cpu_drops_a_game_after_10_s():
    machine = Machine(cpu=90.0)
    count = _count(machine)
    count.first()
    assert count.check(4) is None  # busy, but not for long yet
    machine.now = 9.0
    assert count.check(4) is None
    machine.now = 10.0
    assert count.check(4)[0] == 3
    machine.now = 15.0
    assert count.check(3) is None  # another 10 s for the next one
    machine.now = 20.0
    assert count.check(3)[0] == 2


def test_a_game_joins_after_a_calm_minute():
    machine = Machine()
    count = _count(machine)
    count.first()
    machine.now = 59.0
    assert count.check(2) is None
    machine.now = 60.0
    assert count.check(2)[0] == 3
    machine.now = 100.0
    assert count.check(3) is None  # another minute for the next one
    machine.cpu = 70.0  # not calm: the minute starts again
    machine.now = 130.0
    assert count.check(3) is None
    machine.cpu = 10.0
    machine.now = 140.0
    assert count.check(3) is None
    machine.now = 200.0
    assert count.check(3)[0] == 4
    machine.now = 400.0
    assert count.check(4) is None  # the run's most


def test_other_heavy_jobs_take_cores():
    machine = Machine(others=5)
    count = _count(machine, most=4)
    assert count.first() == 2  # 10 cores - 2 free - 1 training - 5 others
    assert count.check(4)[0] == 3  # more than there's room for: one fewer


@pytest.mark.parametrize("most", [1, 2])
def test_a_check_is_quick(most):
    count = GameCount(most)
    count.first()
    started = time.perf_counter()
    for _ in range(10):
        count.check(most)
    assert time.perf_counter() - started < 1.0  # after every update


# The guard and the command line


def test_the_flag_default_is_the_default_games():
    from absl import flags

    import src.config  # noqa: F401  (defines the flags)

    assert flags.FLAGS["games"].default == game_count.DEFAULT_GAMES


def test_the_guard_expects_the_workers_memory(tmp_path):
    from src.control import guard

    base = guard.estimate_gb(["app.py", "-train", "x", "--games", "1"])
    four = guard.estimate_gb(["app.py", "-train", "x", "--games", "4"])
    assert four == pytest.approx(base + 4 * game_count.GAME_GB)
    default = guard.estimate_gb(["app.py", "-train", "x"])
    assert default == pytest.approx(four)  # --games 4 by default
    assert guard.estimate_gb(["app.py", "-eval", "x"]) == pytest.approx(base)


def test_no_games_is_refused():
    from tests.test_guard_rails import _check

    found = _check(["-train", "probe", "--stage", "box", "--games", "0"])
    assert found == ["--games 0: at least 1"]
