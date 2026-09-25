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
from typing import Callable, Mapping

PROFILE_FORMAT = 1
PROFILES_DIR = Path(__file__).resolve().parents[3] / "rewards"


class RewardProfileError(ValueError):
    pass


@dataclass(frozen=True)
class StepEvents:
    """What happened to the agent's car during one step."""

    points: float  # game points gained (distance and checkpoints)
    checkpoints: int  # checkpoints reached
    crashed: bool  # the car went out this step
    time_up: bool  # the round ended on time this step
    distance: float  # px moved forward (0 when stopped or reversing)
    speed: float  # speed as a fraction of max speed (negative reversing)
    steering_change: float  # how far the steering wheel moved (0 to 2)
    closest_wall: float  # shortest ray, as a fraction of the field diagonal
    # Seconds each checkpoint reached this step had been on the field.
    checkpoint_seconds: tuple[float, ...] = ()
    distance_points: float = 0.0  # game points from driving only


@dataclass(frozen=True)
class Term:
    """One measurable thing per step. Some terms take parameters, each
    with a default (all parameters are positive numbers).
    """

    compute: Callable[[StepEvents, Mapping[str, float]], float]
    params: Mapping[str, float] = MappingProxyType({})

    def __call__(
        self, events: StepEvents, params: Mapping[str, float] | None = None
    ) -> float:
        return self.compute(events, {**self.params, **(params or {})})


def _checkpoint_speed(events: StepEvents, params: Mapping) -> float:
    """1 for a checkpoint reached instantly, down to 0 at `window` s."""
    window = params["window"]
    return sum(
        max(0.0, 1.0 - seconds / window)
        for seconds in events.checkpoint_seconds
    )


# Every term a profile can weight. New terms can be added any time.
TERMS: Mapping[str, Term] = MappingProxyType(
    {
        "points": Term(lambda e, p: e.points),
        "distance_points": Term(lambda e, p: e.distance_points),
        "checkpoints": Term(lambda e, p: e.checkpoints),
        "checkpoint_speed": Term(
            _checkpoint_speed, MappingProxyType({"window": 10.0})
        ),
        "crash": Term(lambda e, p: float(e.crashed)),
        "time_up": Term(lambda e, p: float(e.time_up)),
        "per_step": Term(lambda e, p: 1.0),
        "distance": Term(lambda e, p: e.distance),
        "speed": Term(lambda e, p: e.speed),
        "steering_change": Term(lambda e, p: e.steering_change),
        "closest_wall": Term(lambda e, p: e.closest_wall),
    }
)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


@dataclass(frozen=True)
class RewardProfile:
    name: str
    terms: Mapping[str, float]  # term name -> weight
    description: str = ""  # what the profile is for, in plain words
    # Term name -> parameters given in the file (defaults fill the rest).
    params: Mapping[str, Mapping[str, float]] = MappingProxyType({})
    format: int = PROFILE_FORMAT

    def __call__(self, events: StepEvents) -> float:
        """reward = sum of weight x term."""
        return sum(
            weight * TERMS[term](events, self.params.get(term))
            for term, weight in self.terms.items()
        )

    @staticmethod
    def from_dict(data: dict) -> "RewardProfile":
        """Terms are a weight (`"points": 1.0`), or a weight plus
        parameters (`"checkpoint_speed": {"weight": 100, "window": 10}`).
        """
        if data.get("format") != PROFILE_FORMAT:
            raise RewardProfileError(
                f"unsupported reward profile format {data.get('format')!r}, "
                f"expected {PROFILE_FORMAT}"
            )
        terms = data.get("terms")
        if not terms:
            raise RewardProfileError("a reward profile needs terms")
        weights, params = {}, {}
        for term, spec in terms.items():
            if term not in TERMS:
                known = ", ".join(TERMS)
                raise RewardProfileError(
                    f"unknown reward term {term!r} (known: {known})"
                )
            given = {}
            if isinstance(spec, dict):
                given = {k: v for k, v in spec.items() if k != "weight"}
                spec = spec.get("weight")
            if not _is_number(spec):
                raise RewardProfileError(f"weight of {term!r} must be a number")
            for name, value in given.items():
                if name not in TERMS[term].params:
                    known = ", ".join(TERMS[term].params) or "none"
                    raise RewardProfileError(
                        f"unknown parameter {name!r} for {term!r} "
                        f"(known: {known})"
                    )
                if not _is_number(value) or value <= 0:
                    raise RewardProfileError(
                        f"parameter {name!r} of {term!r} must be positive"
                    )
            weights[term] = float(spec)
            if given:
                params[term] = MappingProxyType(
                    {k: float(v) for k, v in given.items()}
                )
        return RewardProfile(
            name=data["name"],
            terms=MappingProxyType(weights),
            description=data.get("description", ""),
            params=MappingProxyType(params),
        )

    def to_dict(self) -> dict:
        """Plain data, in the file's layout. Replays and runs record it."""
        terms = {
            term: (
                {"weight": weight, **self.params[term]}
                if term in self.params
                else weight
            )
            for term, weight in self.terms.items()
        }
        return {
            "format": self.format,
            "name": self.name,
            "description": self.description,
            "terms": terms,
        }


def load_reward_profile(name_or_path: str) -> RewardProfile:
    """A profile by name (rewards/<name>.json) or by file path."""
    path = Path(name_or_path)
    if path.suffix != ".json":
        path = PROFILES_DIR / f"{name_or_path}.json"
    return RewardProfile.from_dict(json.loads(path.read_text()))
