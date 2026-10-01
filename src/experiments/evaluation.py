"""The evaluation suite: fixed scenarios that score any driver the same
way (roadmap step 5a5, suites/<name>.json).

    round    full rounds on fixed seeds: score, survival, checkpoints
    braking  starts at speed, aimed at a wall: damage-free share

Agents play deterministically, so a checkpoint always gets the same
scores. Results go to agents/<id>/evaluations/<suite>-v<version>.csv, one
row per checkpoint, and the best one to evaluations/best.json.
"""

import csv
import dataclasses
import hashlib
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
from src.config import game_config, get_maze_car_config
from src.drivers.base import Driver
from src.envs.maze_car.env import MazeCarEnv
from src.envs.maze_car.rewards import RewardProfile
from src.sim.components import Health, Hitbox, Motion, PreviousPose
from src.sim.components import Sensors, Transform
from src.sim.resources import Field, SimConfig
from src.sim.rules import load_rules
from src.sim.stage import load_stage
from src.sim.systems.sensors import cast_rays
from src.utils import driving_style, named_files, skills, test_maps
from src.utils.version import code_version

SUITE_FORMAT = 2
SUITES_DIR = Path(__file__).resolve().parents[2] / "suites"
DEFAULT_SUITE = test_maps.SUITE  # "skills"
KINDS = ("round", "braking")
# Scoring plays by the game's points: an agent reward isn't needed.
GAME_POINTS = RewardProfile.from_dict(
    {"format": 1, "name": "game points", "terms": {"points": 1.0}}
)
# A skill's share is the agent's value over the heuristic's, counted as at
# least its floor: one definition, in src/utils/skills.py (7d3b, 7d4).
FLOORS = skills.FLOORS
SKILL = skills.COLUMN  # a skill's column: "skill:open_field"
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
    "share",  # the skills' average share of the heuristic's: the ranking
    *driving_style.COLUMNS,  # how it drives, over the rounds (7c9)
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
    label: str = ""  # the skill as shown: "Open field"
    group: str = ""  # "Handling", "Hunting", "Walls"
    floor: float | None = None  # None: FLOORS[kind]

    @property
    def seeds(self) -> range:
        return range(self.first_seed, self.first_seed + self.episodes)

    @property
    def column(self) -> str:
        return SKILL + self.name

    @property
    def minimum(self) -> float:
        """The least the heuristic's value counts as, for a share."""
        return FLOORS[self.kind] if self.floor is None else self.floor


@dataclass(frozen=True)
class Suite:
    name: str
    version: int
    scenarios: tuple[Scenario, ...]
    description: str = ""

    @property
    def label(self) -> str:
        return f"{self.name}-v{self.version}"

    @property
    def columns(self) -> tuple[str, ...]:
        """A results file's columns: the overall ones, then each skill."""
        return COLUMNS + tuple(s.column for s in self.scenarios)

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
        names = [s.name for s in scenarios]
        if not names:
            raise SuiteError("a suite needs at least one scenario")
        if len(set(names)) != len(names):
            raise SuiteError("each scenario (a skill) needs its own name")
        return Suite(
            name=data["name"],
            version=data["version"],
            scenarios=tuple(scenarios),
            description=data.get("description", ""),
        )


def load_suite(name_or_path: str = DEFAULT_SUITE) -> Suite:
    """A suite by name (suites/<name>.json) or by file path."""
    path = named_files.path_of("suites", name_or_path)
    if not path.exists():
        raise SuiteError(f"no suite file {path}")
    return Suite.from_dict(json.loads(path.read_text()))


# Scoring a driver


def evaluate(
    driver: Driver, suite: Suite, base_config: ConfigDict | None = None
) -> dict:
    """Plays every scenario of the suite. Returns each skill's value (a
    round: its mean game score; braking: the share of clean stops) and the
    overall metrics, over all rounds (each skill weighs the same in the
    mean score).
    """
    result: dict = {}
    games, means, brakes = [], [], []
    style = driving_style.Counter()  # over the rounds, not braking starts
    for scenario in suite.scenarios:
        env = _env(scenario, base_config)
        if scenario.kind == "round":
            played = _round(env, driver, scenario)
            games.extend(played)
            for game in played:
                style.merge(game["style"])
            means.append(statistics.mean(g["score"] for g in played))
            result[scenario.column] = means[-1]
        else:
            result[scenario.column] = _braking(env, driver, scenario)
            brakes.append(result[scenario.column])
    minutes = sum(g["steps"] / g["sps"] for g in games) / 60
    result.update(
        {
            "score_mean": statistics.mean(means) if means else 0.0,
            "score_min": min((g["score"] for g in games), default=0.0),
            "checkpoints_per_min": (
                sum(g["checkpoints"] for g in games) / minutes
                if minutes
                else 0.0
            ),
            "survival": _mean([g["survival"] for g in games]),
            "wreck_rate": _mean([float(g["wrecked"]) for g in games]),
            "contacts": _mean([g["contacts"] for g in games]),
            "braking": _mean(brakes),
            **style.shares(),
        }
    )
    return result


def _mean(values: list) -> float:
    return statistics.mean(values) if values else 0.0


def shares(values: dict, heuristic: dict, suite: Suite) -> dict[str, float]:
    """Each skill's value as a share of the heuristic's (1.0: as good as
    the heuristic), the heuristic's counted as at least the skill's floor.
    """
    return skills.shares(values, heuristic, suite.scenarios)


def average_share(values: dict, heuristic: dict, suite: Suite) -> float:
    found = shares(values, heuristic, suite)
    return statistics.mean(found.values())


def _env(scenario: Scenario, base_config: ConfigDict | None) -> MazeCarEnv:
    config = base_config or get_maze_car_config()
    config = config.copy_and_resolve_references()
    config.show_gui = False
    rules = load_rules(scenario.rules)
    if scenario.round_seconds:
        rules = rules.with_round_seconds(scenario.round_seconds)
    return MazeCarEnv(
        config,
        stage=load_stage(scenario.stage),
        rules=rules,
        driver="Eval",
        reward=GAME_POINTS,  # scoring needs no agent reward (no path work)
    )


def _play(env: MazeCarEnv, driver: Driver, seed: int, setup=None) -> dict:
    observation, _ = env.reset(seed=seed)
    if setup:
        observation = setup(env, seed)
    driver.reset(seed)
    steps = 0
    terminated = truncated = False
    info: dict = {}
    style = driving_style.Counter()
    sps = env.world.resource(SimConfig).steps_per_second
    while not (terminated or truncated):
        action = driver.act(observation)
        observation, _, terminated, truncated, info = env.step(action)
        speed = env.world.component(env.car, Motion).speed * sps
        style.add(action, speed)
        steps += 1
    health = env.world.component(env.car, Health)
    return {
        "steps": steps,
        "score": info["score"],
        "checkpoints": info["checkpoints"],
        "wrecked": terminated,
        "contacts": health.contacts,
        "damage": health.maximum - health.current,
        "style": style,
    }


def _round(env: MazeCarEnv, driver: Driver, scenario: Scenario) -> list:
    """Each game of a round scenario, with its steps per second and the
    share of the round it survived.
    """
    games = [_play(env, driver, seed) for seed in scenario.seeds]
    sps = env.world.resource(SimConfig).steps_per_second
    total = env.rules.round_seconds * sps
    for game in games:
        game["sps"] = sps
        game["survival"] = min(game["steps"] / total, 1.0)
    return games


def _braking(env: MazeCarEnv, driver: Driver, scenario: Scenario) -> float:
    start = scenario.start

    def setup(env, seed):
        place_at_wall(env, random.Random(seed), start)
        return env.last_observation

    games = [_play(env, driver, seed, setup) for seed in scenario.seeds]
    return statistics.mean(float(g["damage"] == 0) for g in games)


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
    values = evaluate(AgentDriver(agent), suite, base_config)
    heuristic = baseline_scores(suite, agent_folder.parent, base_config)[
        "heuristic"
    ]
    row = {
        "checkpoint": checkpoint,
        "decisions": float(agent.decisions),
        **values,
        "share": average_share(values, heuristic, suite),
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
    columns = suite.columns
    with open(path, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: _round_value(r[k]) for k in columns})
    record(
        agent_folder,
        "scored",
        checkpoint=checkpoint,
        suite=suite.label,
        **{k: round(row[k], 4) for k in COLUMNS[2:]},
        skills={s.name: round(row[s.column], 4) for s in suite.scenarios},
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
            share=round(best["share"], 4),
        )
    history = read_history(agent_folder)
    if any(
        e["event"] == "milestone" and e.get("suite") == suite.label
        for e in history
    ):
        return  # once per suite version
    # As good as the heuristic across the skills, and mostly in one piece.
    if best["share"] > 1.0 and best["wreck_rate"] < 0.5:
        record(
            agent_folder,
            "milestone",
            name="first skilled agent",
            checkpoint=best["checkpoint"],
            decisions=best["decisions"],
            suite=suite.label,
            score_mean=round(best["score_mean"], 1),
            share=round(best["share"], 4),
            wreck_rate=round(best["wreck_rate"], 4),
        )


# The code a baseline's scores depend on (7c8): the simulation, the env,
# the baseline drivers, and scoring itself. A commit elsewhere (the control
# center, the docs) keeps the cache.
REPO = Path(__file__).resolve().parents[2]
BASELINE_CODE = (
    "src/ecs",
    "src/sim",
    "src/envs/base.py",
    "src/envs/maze_car",
    "src/drivers/actions.py",
    "src/drivers/base.py",
    "src/drivers/heuristic.py",
    "src/drivers/random_driver.py",
    "src/experiments/evaluation.py",
)


def baseline_fingerprint(
    suite: Suite, base_config: ConfigDict | None = None
) -> str:
    """A hash of everything the baselines' scores depend on: that code,
    the game settings in effect, and the suite with its maps and rules.
    """
    digest = hashlib.sha256()
    for entry in BASELINE_CODE:
        path = REPO / entry
        files = sorted(path.rglob("*.py")) if path.is_dir() else [path]
        for file in files:
            digest.update(str(file.relative_to(REPO)).encode())
            digest.update(file.read_bytes())
    config = base_config or get_maze_car_config()
    digest.update(json.dumps(game_config(config), sort_keys=True).encode())
    digest.update(json.dumps(_suite_data(suite), sort_keys=True).encode())
    for scenario in suite.scenarios:
        for kind, name in (
            ("stages", scenario.stage),
            ("rules", scenario.rules),
        ):
            digest.update(named_files.path_of(kind, name).read_bytes())
    return digest.hexdigest()[:16]


def _suite_data(suite: Suite) -> dict:
    return {
        "label": suite.label,
        "scenarios": [dataclasses.asdict(s) for s in suite.scenarios],
    }


def baseline_scores(
    suite: Suite, agents_root: Path, base_config: ConfigDict | None = None
) -> dict[str, dict]:
    """The heuristic's and random driver's scores on the suite, cached in
    <agents root>/baselines/<suite>-v<version>.json until anything they
    depend on changes (`baseline_fingerprint`).
    """
    from src.drivers.heuristic import CompassDriver
    from src.drivers.random_driver import RandomDriver

    path = Path(agents_root) / "baselines" / f"{suite.label}.json"
    fingerprint = baseline_fingerprint(suite, base_config)
    if path.exists():
        cached = json.loads(path.read_text())
        if cached.get("fingerprint") == fingerprint:
            return cached["scores"]
    scores = {
        "heuristic": evaluate(CompassDriver(), suite, base_config),
        "random": evaluate(RandomDriver(), suite, base_config),
    }
    for values in scores.values():  # the heuristic's is about 1.0
        values["share"] = average_share(values, scores["heuristic"], suite)
    path.parent.mkdir(parents=True, exist_ok=True)
    cache = {"fingerprint": fingerprint, "code": code_version()}
    path.write_text(json.dumps({**cache, "scores": scores}, indent=2) + "\n")
    return scores


def unscored(folder: Path, suite: Suite) -> list[str]:
    """The agent's checkpoints not yet scored with this suite version,
    oldest first.
    """
    done = {r["checkpoint"] for r in read_results(folder, suite)}
    checkpoints = sorted(
        (folder / "checkpoints").glob("*.pt"),
        key=lambda p: p.stat().st_mtime_ns,
    )
    return [p.stem for p in checkpoints if p.stem not in done]


def baselines_fresh(
    suite: Suite, agents_root: Path, base_config: ConfigDict | None = None
) -> bool:
    """Whether the baselines' cache still holds (no 9 s of scoring)."""
    path = Path(agents_root) / "baselines" / f"{suite.label}.json"
    if not path.exists():
        return False
    cached = json.loads(path.read_text())
    fingerprint = baseline_fingerprint(suite, base_config)
    return cached.get("fingerprint") == fingerprint


def evaluate_agent(
    agent: str | Path,
    suite: Suite,
    root: Path | None = None,
    base_config: ConfigDict | None = None,
    on_checkpoint=None,
    on_start=None,
) -> list[dict]:
    """Scores every checkpoint of an agent not yet scored with this suite
    version. Returns all rows, oldest first. `on_start(checkpoint, i, n)`
    comes before each one (i from 1), `on_checkpoint(row)` after.
    """
    folder = load_agent(agent, "initial", root=root).folder
    todo = unscored(folder, suite)
    for i, name in enumerate(todo, start=1):
        if on_start:
            on_start(name, i, len(todo))
        row = evaluate_checkpoint(folder, name, suite, base_config)
        if on_checkpoint:
            on_checkpoint(row)
    return read_results(folder, suite)


def best_row(rows: list[dict]) -> dict:
    """The best average share of the heuristic across the skills; ties go
    to better survival.
    """
    return max(rows, key=lambda r: (r["share"], r["survival"]))


def _round_value(value):
    return round(value, 4) if isinstance(value, float) else value


def format_results(
    rows: list[dict], baselines: dict[str, dict] | None = None
) -> str:
    header = (
        f"  {'checkpoint':12s} {'decisions':>10s} {'score':>7s} "
        f"{'worst':>7s} {'cp/min':>6s} {'surv':>5s} {'wrecks':>6s} "
        f"{'walls':>5s} {'brake':>5s} {'share':>5s}"
    )
    lines = [header]

    def line(name, decisions, r, mark=" "):
        return (
            f"{mark} {name:12s} {decisions:>10s} {r['score_mean']:>7,.0f} "
            f"{r['score_min']:>7,.0f} {r['checkpoints_per_min']:>6.1f} "
            f"{r['survival']:>5.0%} {r['wreck_rate']:>6.0%} "
            f"{r['contacts']:>5.1f} {r['braking']:>5.0%} "
            f"{r['share']:>5.2f}"
        )

    for name, r in (baselines or {}).items():
        lines.append(line(name, "baseline", r))
    best = best_row(rows)["checkpoint"] if rows else None
    for r in rows:
        mark = "*" if r["checkpoint"] == best else " "
        lines.append(line(r["checkpoint"], f"{r['decisions']:,.0f}", r, mark))
    if best:
        lines.append(
            f"* best: {best} (the best average share of the heuristic's "
            "score across the skills)"
        )
    return "\n".join(lines)
