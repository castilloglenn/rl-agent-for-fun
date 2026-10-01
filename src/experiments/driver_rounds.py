"""A driver's rounds as recordings (roadmap 7c15): plays a driver (the
heuristic, by default) headless and saves every round to
`recordings/<Player>/`, like your own rounds, so an imitation dataset
can learn from it (`datasets/heuristic.json`): imitate the heuristic
first, then train with RL.

    python app.py -record_rounds heuristic --stage basics --rounds 50

A mix plays its maps in turn, one per round. Round i uses seed
first_seed + i (the suite's seeds start at 1,000,000, so they never
meet).
"""

from pathlib import Path
from typing import Callable

from ml_collections import ConfigDict

from src.drivers.episode import EpisodeResult, run_episode
from src.drivers.registry import DriverError, make_driver
from src.envs.maze_car.env import MazeCarEnv
from src.replay.recordings import KEEP_LATEST, LibraryRecorder
from src.replay.recordings import RecordingLibrary
from src.sim.rules import Rules
from src.sim.stage import load_stage
from src.utils.mixes import stages_of

ROUNDS = 50


def player_of(driver: str) -> str:
    """The recordings' player for a driver: "heuristic" -> "Heuristic"."""
    name = driver.removeprefix("agent:").replace("@", "_")
    return name[:1].upper() + name[1:]


def record_rounds(
    driver: str,
    config: ConfigDict,
    rounds: int = ROUNDS,
    first_seed: int = 0,
    rules: Rules | None = None,
    root: Path | None = None,
    on_round: Callable[[int, str, EpisodeResult], None] | None = None,
) -> list[Path]:
    """Plays `rounds` rounds with `driver` on `config.stage` (a stage or
    a mix) and saves each to its player's recordings. Returns the paths.
    The library keeps at least `rounds` of them (older ones beyond that
    are pruned, as for your own).
    """
    if driver == "keyboard":
        raise DriverError("the keyboard needs the window: drive instead")
    player = make_driver(driver)
    config = config.copy_and_resolve_references()
    config.show_gui = False
    stages = [load_stage(name) for name in stages_of(config.stage)]
    library = RecordingLibrary(
        player_of(driver), root=root, limit=max(KEEP_LATEST, rounds)
    )
    recorder = LibraryRecorder({"1": player.record()}, library)
    env = MazeCarEnv(
        config,
        driver=player.label,
        rules=rules,
        stage=stages[0],
        recorder=recorder,
    )
    saved = []
    for i in range(rounds):
        stage = stages[i % len(stages)]
        env.stage = stage
        recorder.last_saved = None
        result = run_episode(env, player, seed=first_seed + i)
        if recorder.last_saved:
            saved.append(recorder.last_saved)
        if on_round:
            on_round(i, stage.name, result)
    return saved
