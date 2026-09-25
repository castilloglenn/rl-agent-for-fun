"""Re-simulates a replay exactly, from the file alone, and verifies it.

The replay's embedded stage, seed, game-defining config, and reward
profile rebuild the same game. The simulation is deterministic, so the
same inputs must reproduce the end line. A mismatch means the simulation
changed since recording: the replay is out of date, and says so.
"""

from dataclasses import dataclass, field

from src.config import config_with_game
from src.envs.maze_car.env import MazeCarEnv
from src.envs.maze_car.rewards import RewardProfile
from src.replay.format import Replay, to_current_actions
from src.sim.components import Score
from src.sim.resources import RoundState, SimClock
from src.sim.stage import Stage
from src.utils.version import code_version


@dataclass(frozen=True)
class Verification:
    ok: bool
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # not failures


def driver_label(driver: dict) -> str:
    if driver.get("type") == "human":
        return f"{driver.get('player', 'player')} (replay)"
    if driver.get("type") == "agent":
        return f"{driver.get('id', 'agent')} (replay)"
    return "Replay"


class Replayer:
    def __init__(self, replay: Replay, show_gui: bool = False) -> None:
        self.replay = replay
        header = replay.header
        config = config_with_game(header["config"])
        config.show_gui = show_gui
        self.env = MazeCarEnv(
            config,
            driver=driver_label(replay.slots["1"]),
            reward=RewardProfile.from_dict(header["reward"]),
            stage=Stage.from_dict(header["stage"]),
        )
        self.env.reset(seed=header["seed"])

        if replay.end is not None:
            self.total_steps = replay.end["step"]
        elif replay.changes:
            self.total_steps = replay.changes[-1][0] + 1
        else:
            self.total_steps = 0
        self._actions = replay.actions_by_step(self.total_steps)
        self.step_index = 0

    @property
    def done(self) -> bool:
        return self.step_index >= self.total_steps

    def step(self) -> bool:
        """Re-simulates one step. Returns False once the replay is over."""
        if self.done:
            return False
        stored = self._actions[self.step_index].get("1", [])
        action = to_current_actions(
            stored, self.replay.action_names, self.env.action_names
        )
        self.env.step_world(action)
        self.step_index += 1
        return not self.done

    def run(self) -> Verification:
        """Re-simulates to the end, then verifies."""
        while self.step():
            pass
        return self.verify()

    def verify(self) -> Verification:
        end = self.replay.end
        notes = self._notes()
        if end is None:
            return Verification(False, ["the replay has no end line"], notes)

        world = self.env.world
        problems = []
        step = world.resource(SimClock).step
        if step != end["step"]:
            problems.append(f"ended at step {step}, expected {end['step']}")
        state = world.resource(RoundState)
        if end["reason"] == "stopped":
            if state.over:
                problems.append("the round ended, but it was stopped")
        elif state.reason != end["reason"]:
            problems.append(
                f"round ended by {state.reason!r}, expected {end['reason']!r}"
            )
        score = world.component(self.env.car, Score).total
        if score != end["scores"]["1"]:
            problems.append(f"score {score}, expected {end['scores']['1']}")
        if self.env.round_reward != end["rewards"]["1"]:
            problems.append(
                f"reward {self.env.round_reward}, "
                f"expected {end['rewards']['1']}"
            )
        return Verification(not problems, problems, notes)

    def _notes(self) -> list[str]:
        header = self.replay.header
        notes = []
        if header.get("code") != code_version():
            notes.append(
                f"recorded with code {header.get('code')}, "
                f"now {code_version()}"
            )
        if header.get("observation_version") != self.env.observation_version:
            notes.append(
                f"observation version {header.get('observation_version')}, "
                f"now {self.env.observation_version}"
            )
        return notes
