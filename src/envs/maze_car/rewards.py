"""Reward profiles: what an agent learns from, kept apart from the game
score.

The game score (HUD, leaderboards) has fixed rules. A reward profile is a
weighted sum of per-step terms, stored as a file in rewards/, so
experiments can reward things differently without touching the game. See
docs/decisions/011-reward-profiles.md.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Callable

PROFILE_FORMAT = 1
PROFILES_DIR = Path(__file__).resolve().parents[3] / "rewards"


class RewardProfileError(ValueError):
    pass


@dataclass(frozen=True)
class StepEvents:
    """What happened to the agent's car during one step."""

    points: float  # game points gained
    checkpoints: int  # checkpoints reached
    crashed: bool  # the car went out this step
    time_up: bool  # the round ended on time this step
    distance: float  # px moved forward (0 when stopped or reversing)
    speed: float  # speed as a fraction of max speed (negative reversing)
    steering_change: float  # how far the steering wheel moved (0 to 2)
    closest_wall: float  # shortest ray, as a fraction of the field diagonal


# Every term a profile can weight. New terms can be added any time.
TERMS: MappingProxyType[str, Callable[[StepEvents], float]] = MappingProxyType(
    {
        "points": lambda e: e.points,
        "checkpoints": lambda e: e.checkpoints,
        "crash": lambda e: float(e.crashed),
        "time_up": lambda e: float(e.time_up),
        "per_step": lambda e: 1.0,
        "distance": lambda e: e.distance,
        "speed": lambda e: e.speed,
        "steering_change": lambda e: e.steering_change,
        "closest_wall": lambda e: e.closest_wall,
    }
)


@dataclass(frozen=True)
class RewardProfile:
    name: str
    terms: MappingProxyType  # term name -> weight
    format: int = PROFILE_FORMAT

    def __call__(self, events: StepEvents) -> float:
        """reward = sum of weight x term."""
        return sum(
            weight * TERMS[term](events) for term, weight in self.terms.items()
        )

    @staticmethod
    def from_dict(data: dict) -> "RewardProfile":
        if data.get("format") != PROFILE_FORMAT:
            raise RewardProfileError(
                f"unsupported reward profile format {data.get('format')!r}, "
                f"expected {PROFILE_FORMAT}"
            )
        terms = data.get("terms")
        if not terms:
            raise RewardProfileError("a reward profile needs terms")
        for term, weight in terms.items():
            if term not in TERMS:
                known = ", ".join(TERMS)
                raise RewardProfileError(
                    f"unknown reward term {term!r} (known: {known})"
                )
            if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                raise RewardProfileError(f"weight of {term!r} must be a number")
        return RewardProfile(
            name=data["name"],
            terms=MappingProxyType({t: float(w) for t, w in terms.items()}),
        )

    def to_dict(self) -> dict:
        """Plain data, in the file's layout. Replays and runs record it."""
        return {
            "format": self.format,
            "name": self.name,
            "terms": dict(self.terms),
        }


def load_reward_profile(name_or_path: str) -> RewardProfile:
    """A profile by name (rewards/<name>.json) or by file path."""
    path = Path(name_or_path)
    if path.suffix != ".json":
        path = PROFILES_DIR / f"{name_or_path}.json"
    return RewardProfile.from_dict(json.loads(path.read_text()))
