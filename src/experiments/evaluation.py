"""The evaluation suite: fixed scenarios that score any driver the same
way (roadmap step 5a5, suites/<name>.json).

    round    full rounds on fixed seeds: score, survival, checkpoints
    braking  starts at speed, aimed at a wall: damage-free share

Agents play deterministically, so a checkpoint always gets the same
scores. Results go to agents/<id>/evaluations/<suite>-v<version>.csv, one
row per checkpoint, and the best one to evaluations/best.json.
"""

import csv
import json
import math
import random
import statistics
from dataclasses import dataclass
from pathlib import Path

from ml_collections import ConfigDict

from src.agents.driver import AgentDriver
from src.agents.history import BEST_FILE, read_history, record
from src.agents.store import load_agent
from src.config import get_maze_car_config
from src.drivers.base import Driver
from src.envs.maze_car.env import MazeCarEnv
from src.sim.components import Health, Hitbox, Motion, PreviousPose
from src.sim.components import Sensors, Transform
from src.sim.resources import Field, SimConfig
from src.sim.rules import load_rules
from src.sim.stage import load_stage
from src.sim.systems.sensors import cast_rays
from src.utils.version import code_version

SUITE_FORMAT = 1
SUITES_DIR = Path(__file__).resolve().parents[2] / "suites"
DEFAULT_SUITE = "box"
KINDS = ("round", "braking")
COLUMNS = (
    "checkpoint",
    "decisions",
    "score_mean",
    "score_min",
    "checkpoints_per_min",
    "survival",  # share of the round survived
    "wreck_rate",
    "contacts",  # per round
    "braking",  # share of braking starts with no damage
)


class SuiteError(ValueError):
    pass


@dataclass(frozen=True)
class Scenario:
    name: str
    kind: str
    stage: str
    rules: str
    first_seed: int
    episodes: int
    round_seconds: float = 0.0  # 0 = the rules' own
    start: dict | None = None  # braking: speed, distances, max angle

    @property
    def seeds(self) -> range:
        return range(self.first_seed, self.first_seed + self.episodes)


@dataclass(frozen=True)
class Suite:
    name: str
    version: int
    scenarios: tuple[Scenario, ...]
    description: str = ""

    @property
    def label(self) -> str:
        return f"{self.name}-v{self.version}"

    @staticmethod
    def from_dict(data: dict) -> "Suite":
        if data.get("format") != SUITE_FORMAT:
            raise SuiteError(f"unsupported suite format {data.get('format')!r}")
        scenarios = []
        for item in data["scenarios"]:
            scenario = Scenario(**item)
            if scenario.kind not in KINDS:
                raise SuiteError(
                    f"unknown scenario kind {scenario.kind!r} "
                    f"(known: {', '.join(KINDS)})"
                )
            if scenario.episodes < 1:
                raise SuiteError(f"{scenario.name}: episodes must be >= 1")
            if scenario.kind == "braking" and not scenario.start:
                raise SuiteError(f"{scenario.name}: braking needs a start")
            scenarios.append(scenario)
        kinds = [s.kind for s in scenarios]
        if sorted(kinds) != sorted(KINDS):
            raise SuiteError("a suite needs one round and one braking scenario")
        return Suite(
            name=data["name"],
            version=data["version"],
            scenarios=tuple(scenarios),
            description=data.get("description", ""),
        )


def load_suite(name_or_path: str = DEFAULT_SUITE) -> Suite:
    """A suite by name (suites/<name>.json) or by file path."""
    path = Path(name_or_path)
    if path.suffix != ".json":
        path = SUITES_DIR / f"{name_or_path}.json"
    if not path.exists():
        raise SuiteError(f"no suite file {path}")
    return Suite.from_dict(json.loads(path.read_text()))


# Scoring a driver


def evaluate(
    driver: Driver, suite: Suite, base_config: ConfigDict | None = None
) -> dict:
    """Plays every scenario of the suite. Returns one value per metric."""
    result: dict = {}
    for scenario in suite.scenarios:
        env = _env(scenario, base_config)
        if scenario.kind == "round":
            result.update(_round(env, driver, scenario))
        else:
            result.update(_braking(env, driver, scenario))
    return result


def _env(scenario: Scenario, base_config: ConfigDict | None) -> MazeCarEnv:
    config = base_config or get_maze_car_config()
    config = config.copy_and_resolve_references()
    config.show_gui = False
    rules = load_rules(scenario.rules)
    if scenario.round_seconds:
        rules = rules.with_round_seconds(scenario.round_seconds)
    return MazeCarEnv(
        config, stage=load_stage(scenario.stage), rules=rules, driver="Eval"
    )


def _play(env: MazeCarEnv, driver: Driver, seed: int, setup=None) -> dict:
    observation, _ = env.reset(seed=seed)
    if setup:
        observation = setup(env, seed)
    driver.reset(seed)
    steps = 0
    terminated = truncated = False
    info: dict = {}
    while not (terminated or truncated):
        observation, _, terminated, truncated, info = env.step(
            driver.act(observation)
        )
        steps += 1
    health = env.world.component(env.car, Health)
    return {
        "steps": steps,
        "score": info["score"],
        "checkpoints": info["checkpoints"],
        "wrecked": terminated,
        "contacts": health.contacts,
        "damage": health.maximum - health.current,
    }


def _round(env: MazeCarEnv, driver: Driver, scenario: Scenario) -> dict:
    games = [_play(env, driver, seed) for seed in scenario.seeds]
    sps = env.world.resource(SimConfig).steps_per_second
    total = env.rules.round_seconds * sps
    minutes = sum(g["steps"] for g in games) / sps / 60
    return {
        "score_mean": statistics.mean(g["score"] for g in games),
        "score_min": min(g["score"] for g in games),
        "checkpoints_per_min": sum(g["checkpoints"] for g in games) / minutes,
        "survival": statistics.mean(
            min(g["steps"] / total, 1.0) for g in games
        ),
        "wreck_rate": statistics.mean(float(g["wrecked"]) for g in games),
        "contacts": statistics.mean(g["contacts"] for g in games),
    }


def _braking(env: MazeCarEnv, driver: Driver, scenario: Scenario) -> dict:
    start = scenario.start

    def setup(env, seed):
        place_at_wall(env, random.Random(seed), start)
        return env.last_observation

    games = [_play(env, driver, seed, setup) for seed in scenario.seeds]
    return {"braking": statistics.mean(float(g["damage"] == 0) for g in games)}


def place_at_wall(env: MazeCarEnv, rng: random.Random, start: dict) -> None:
    """Puts the car at `start["speed"]` px/s, its nose min to max distance
    from a wall along its heading, up to max_angle off head-on. The wall,
    distance, angle, and side come from `rng`.
    """
    world, car = env.world, env.car
    field = world.resource(Field).rect
    half = world.component(car, Hitbox).width / 2
    wall = rng.choice(("right", "top", "left", "bottom"))
    distance = rng.uniform(start["min_distance"], start["max_distance"])
    off = rng.uniform(-start["max_angle"], start["max_angle"])
    along = rng.uniform(0.3, 0.7)  # where along the wall, away from corners
    normal = {"right": 0.0, "top": 90.0, "left": 180.0, "bottom": 270.0}[wall]
    heading = (normal + off) % 360
    dx, dy = math.cos(math.radians(heading)), -math.sin(math.radians(heading))
    gap = distance * math.cos(math.radians(off))  # nose to wall, straight
    if wall == "right":
        nose = (field.right - gap, field.top + along * field.height)
    elif wall == "left":
        nose = (field.left + gap, field.top + along * field.height)
    elif wall == "top":
        nose = (field.left + along * field.width, field.top + gap)
    else:
        nose = (field.left + along * field.width, field.bottom - gap)
    transform = world.component(car, Transform)
    transform.x, transform.y = nose[0] - half * dx, nose[1] - half * dy
    transform.angle = heading
    world.add_component(
        car, PreviousPose(transform.x, transform.y, transform.angle)
    )
    sim = world.resource(SimConfig)
    world.component(car, Motion).speed = start["speed"] / sim.steps_per_second
    sensors = world.component(car, Sensors)
    cast_rays(sensors, transform, world.resource(Field), sim.ray_length)
    env.last_observation = env.get_state()


# Scoring an agent's checkpoints


def results_path(agent_folder: Path, suite: Suite) -> Path:
    return agent_folder / "evaluations" / f"{suite.label}.csv"


def read_results(agent_folder: Path, suite: Suite) -> list[dict]:
    path = results_path(agent_folder, suite)
    if not path.exists():
        return []
    with open(path, newline="") as file:
        return [
            {k: v if k == "checkpoint" else float(v) for k, v in row.items()}
            for row in csv.DictReader(file)
        ]


def evaluate_checkpoint(
    agent_folder: Path,
    checkpoint: str,
    suite: Suite,
    base_config: ConfigDict | None = None,
) -> dict:
    """Scores one checkpoint, saves (or replaces) its row, and updates
    the best checkpoint.
    """
    agent = load_agent(agent_folder, checkpoint)
    row = {
        "checkpoint": checkpoint,
        "decisions": float(agent.decisions),
        **evaluate(AgentDriver(agent), suite, base_config),
    }
    rows = [
        r
        for r in read_results(agent_folder, suite)
        if r["checkpoint"] != checkpoint
    ]
    rows.append(row)
    rows.sort(key=lambda r: (r["decisions"], r["checkpoint"]))
    path = results_path(agent_folder, suite)
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: _round_value(r[k]) for k in COLUMNS})
    record(
        agent_folder,
        "scored",
        checkpoint=checkpoint,
        suite=suite.label,
        **{k: round(row[k], 4) for k in COLUMNS[2:]},
    )
    if suite.name == DEFAULT_SUITE:
        _update_best(agent_folder, suite, rows, base_config)
    return row


def _update_best(agent_folder, suite, rows, base_config) -> None:
    """Saves the best checkpoint, and records the milestone once the best
    one first beats the heuristic and survives most rounds.
    """
    path = agent_folder / BEST_FILE
    before = None
    if path.exists():
        before = json.loads(path.read_text())["checkpoint"]
    best = best_row(rows)
    path.write_text(
        json.dumps({"suite": suite.label, "checkpoint": best["checkpoint"]})
        + "\n"
    )
    if best["checkpoint"] != before:
        record(
            agent_folder,
            "new_best",
            checkpoint=best["checkpoint"],
            suite=suite.label,
            score_mean=round(best["score_mean"], 1),
        )
    if any(e["event"] == "milestone" for e in read_history(agent_folder)):
        return
    heuristic = baseline_scores(suite, agent_folder.parent, base_config)[
        "heuristic"
    ]
    beats = best["score_mean"] > heuristic["score_mean"]
    if beats and best["wreck_rate"] < 0.5:
        record(
            agent_folder,
            "milestone",
            name="first skilled agent",
            checkpoint=best["checkpoint"],
            decisions=best["decisions"],
            suite=suite.label,
            score_mean=round(best["score_mean"], 1),
            wreck_rate=round(best["wreck_rate"], 4),
            heuristic_score=round(heuristic["score_mean"], 1),
        )


def baseline_scores(
    suite: Suite, agents_root: Path, base_config: ConfigDict | None = None
) -> dict[str, dict]:
    """The heuristic's and random driver's scores on the suite, cached in
    <agents root>/baselines/<suite>-v<version>.json for this code version.
    """
    from src.drivers.heuristic import CompassDriver
    from src.drivers.random_driver import RandomDriver

    path = Path(agents_root) / "baselines" / f"{suite.label}.json"
    if path.exists():
        cached = json.loads(path.read_text())
        if cached.get("code") == code_version():
            return cached["scores"]
    scores = {
        "heuristic": evaluate(CompassDriver(), suite, base_config),
        "random": evaluate(RandomDriver(), suite, base_config),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"code": code_version(), "scores": scores}, indent=2) + "\n"
    )
    return scores


def evaluate_agent(
    agent: str | Path,
    suite: Suite,
    root: Path | None = None,
    base_config: ConfigDict | None = None,
    on_checkpoint=None,
) -> list[dict]:
    """Scores every checkpoint of an agent not yet scored with this suite
    version. Returns all rows, oldest first.
    """
    folder = load_agent(agent, "initial", root=root).folder
    done = {r["checkpoint"] for r in read_results(folder, suite)}
    checkpoints = sorted(
        (folder / "checkpoints").glob("*.pt"),
        key=lambda p: p.stat().st_mtime_ns,
    )
    for path in checkpoints:
        if path.stem not in done:
            row = evaluate_checkpoint(folder, path.stem, suite, base_config)
            if on_checkpoint:
                on_checkpoint(row)
    return read_results(folder, suite)


def best_row(rows: list[dict]) -> dict:
    """Highest mean round score; ties go to better survival."""
    return max(rows, key=lambda r: (r["score_mean"], r["survival"]))


def _round_value(value):
    return round(value, 4) if isinstance(value, float) else value


def format_results(
    rows: list[dict], baselines: dict[str, dict] | None = None
) -> str:
    header = (
        f"  {'checkpoint':12s} {'decisions':>10s} {'score':>7s} "
        f"{'worst':>7s} {'cp/min':>6s} {'surv':>5s} {'wrecks':>6s} "
        f"{'walls':>5s} {'brake':>5s}"
    )
    lines = [header]

    def line(name, decisions, r, mark=" "):
        return (
            f"{mark} {name:12s} {decisions:>10s} {r['score_mean']:>7,.0f} "
            f"{r['score_min']:>7,.0f} {r['checkpoints_per_min']:>6.1f} "
            f"{r['survival']:>5.0%} {r['wreck_rate']:>6.0%} "
            f"{r['contacts']:>5.1f} {r['braking']:>5.0%}"
        )

    for name, r in (baselines or {}).items():
        lines.append(line(name, "baseline", r))
    best = best_row(rows)["checkpoint"] if rows else None
    for r in rows:
        mark = "*" if r["checkpoint"] == best else " "
        lines.append(line(r["checkpoint"], f"{r['decisions']:,.0f}", r, mark))
    if best:
        lines.append(f"* best: {best} (highest mean round score)")
    return "\n".join(lines)
