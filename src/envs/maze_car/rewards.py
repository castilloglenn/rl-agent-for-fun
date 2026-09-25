"""Agent reward functions, kept apart from the game score.

The game score (HUD, leaderboards) has fixed rules. The agent reward is
what an agent learns from, and experiments may change it (for example a
crash penalty) without touching the game. See
docs/decisions/010-decouple-before-file-formats.md.
"""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class StepEvents:
    """What happened to the agent's car during one step."""

    points: float  # game score gained
    checkpoints: int  # checkpoints reached
    crashed: bool  # the car went out this step
    time_up: bool  # the round ended on time this step


RewardFunction = Callable[[StepEvents], float]


def points_gained(events: StepEvents) -> float:
    """The default: the agent reward equals the game score gained."""
    return events.points


REWARD_FUNCTIONS: dict[str, RewardFunction] = {
    "points_gained": points_gained,
}
