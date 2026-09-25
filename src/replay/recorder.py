"""Records an env's games as replays.

Attach it with `env.recorder = ReplayRecorder(drivers)`. The env calls
`on_reset`, `on_step`, and `on_finish`, and never imports this module.
"""

from datetime import datetime, timezone

from src.config import game_config
from src.replay.format import REPLAY_FORMAT, Replay, write_replay
from src.sim.components import Score
from src.sim.resources import RoundState, Rng, SimClock, SimConfig
from src.sim.stage import Stage
from src.utils.version import code_version


def human_driver(player: str, device: str = "keyboard") -> dict:
    return {"type": "human", "player": player, "device": device}


def agent_driver(agent_id: str, checkpoint: str | None = None) -> dict:
    return {"type": "agent", "id": agent_id, "checkpoint": checkpoint}


class ReplayRecorder:
    """Keeps the replay of the env's current game in memory.

    drivers: the driver record per slot, for example
    {"1": human_driver("zen")}.
    """

    def __init__(self, drivers: dict[str, dict]) -> None:
        self.drivers = drivers
        self.replay: Replay | None = None
        self._last: dict[str, list[bool]] = {}

    def on_reset(self, env) -> None:
        world = env.world
        self.replay = Replay(
            header={
                "format": REPLAY_FORMAT,
                "recorded_at": datetime.now(timezone.utc).isoformat(
                    timespec="seconds"
                ),
                "code": code_version(),
                "stage": world.resource(Stage).to_dict(),
                "seed": world.resource(Rng).seed,
                "config": game_config(env.config),
                "reward": env.reward_profile.to_dict(),
                "slots": self.drivers,
                "action_names": list(env.action_names),
                "observation_version": env.observation_version,
                "steps_per_second": world.resource(SimConfig).steps_per_second,
            }
        )
        self._last = {}

    def on_step(self, step: int, actions: dict[str, tuple]) -> None:
        """Called before the world steps. Stores only changed actions."""
        # Plain bools: agents may pass numpy bools, which JSON can't write.
        plain = {
            slot: [bool(pressed) for pressed in action]
            for slot, action in actions.items()
        }
        changed = {
            slot: action
            for slot, action in plain.items()
            if self._last.get(slot) != action
        }
        if changed:
            self.replay.changes.append((step, changed))
            self._last.update(changed)

    def on_finish(self, env, reason: str | None = None) -> None:
        """Writes the end line: what re-simulation must reproduce."""
        state = env.world.resource(RoundState)
        self.replay.end = {
            "step": env.world.resource(SimClock).step,
            "reason": reason or state.reason,
            "scores": {
                slot: env.world.component(env.car, Score).total
                for slot in self.drivers
            },
            "rewards": {slot: env.round_reward for slot in self.drivers},
        }

    @property
    def finished(self) -> bool:
        return self.replay is not None and self.replay.end is not None

    def save(self, path) -> None:
        write_replay(self.replay, path)
