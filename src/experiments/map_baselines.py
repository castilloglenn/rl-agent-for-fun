"""The heuristic's fuels a minute on each training map (7f5): the
bar a curriculum's level is judged against, on the maps it trains on,
never the skills suite's test maps.

    <agents root>/baselines/maps.json   {key: rate}

A map's key is its name, the rules, and a hash of everything the rate
depends on (the simulation and baseline drivers' code, the game settings,
the map's and the rules' content), so it's measured once, again only
after any of that changes.
"""

import hashlib
import json
from pathlib import Path

from ml_collections import ConfigDict

from src.config import game_config, get_maze_car_config
from src.drivers.episode import run_episode
from src.drivers.heuristic import CompassDriver
from src.envs.maze_car.env import MazeCarEnv
from src.experiments.evaluation import BASELINE_CODE, REPO
from src.sim.rules import Rules
from src.sim.stage import load_stage
from src.utils import named_files

ROUNDS = 3  # rounds per map
FIRST_SEED = 9_000_000  # apart from training's and the suite's seeds


def heuristic_rates(
    stages: list[str],
    rules: Rules,
    agents_root: Path,
    base_config: ConfigDict | None = None,
) -> dict[str, float]:
    """{map: the heuristic's fuels a minute there}, cached."""
    path = Path(agents_root) / "baselines" / "maps.json"
    try:
        cache = json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        cache = {}
    config = base_config or get_maze_car_config()
    config = config.copy_and_resolve_references()
    config.show_gui = False
    code = _code_digest()
    found, changed = {}, False
    for i, stage in enumerate(stages):
        key = f"{stage}|{rules.name}|{_digest(code, stage, rules, config)}"
        if key not in cache:
            # The Runs tab's starting row shows this line (7c16).
            print(
                f"Measuring the heuristic on {stage} ({i + 1} of "
                f"{len(stages)}), once for the curriculum's goals",
                flush=True,
            )
            cache[key] = _measure(stage, rules, config)
            changed = True
        found[stage] = cache[key]
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n")
    return found


def _measure(stage: str, rules: Rules, config: ConfigDict) -> float:
    env = MazeCarEnv(config, stage=load_stage(stage), rules=rules)
    fuels = steps = 0
    for i in range(ROUNDS):
        result = run_episode(env, CompassDriver(), FIRST_SEED + i)
        fuels += result.fuels
        steps += result.steps
    minutes = steps / env.config.sim.steps_per_second / 60
    return round(fuels / max(minutes, 1e-6), 4)


def _code_digest() -> str:
    digest = hashlib.sha256()
    for entry in BASELINE_CODE:
        path = REPO / entry
        files = sorted(path.rglob("*.py")) if path.is_dir() else [path]
        for file in files:
            digest.update(str(file.relative_to(REPO)).encode())
            digest.update(file.read_bytes())
    return digest.hexdigest()


def _digest(code: str, stage: str, rules: Rules, config) -> str:
    digest = hashlib.sha256(code.encode())
    digest.update(json.dumps(game_config(config), sort_keys=True).encode())
    digest.update(named_files.path_of("stages", stage).read_bytes())
    digest.update(json.dumps(rules.to_dict(), sort_keys=True).encode())
    return digest.hexdigest()[:16]
