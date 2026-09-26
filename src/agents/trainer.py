"""Trainer files: how an agent learns, changeable per training phase
(decision 014).
"""

import json
from dataclasses import MISSING, asdict, dataclass
from pathlib import Path

TRAINER_FORMAT = 1
TRAINERS_DIR = Path(__file__).resolve().parents[2] / "trainers"
ALGORITHMS = ("ppo",)


class TrainerError(ValueError):
    pass


@dataclass(frozen=True)
class TrainerSpec:
    name: str
    algorithm: str
    learning_rate: float
    gamma: float  # discount: how far ahead the agent cares
    gae_lambda: float  # smoothing of the advantage estimate
    clip: float  # how far one update may move the policy
    entropy: float  # exploration bonus
    value_coef: float
    max_grad_norm: float
    rollout: int  # decisions collected per update
    minibatch: int
    epochs: int
    total_decisions: int  # length of the training phase
    checkpoint_every: int  # decisions between saved weights
    seed: int  # action sampling and minibatch order
    # The learner sees rewards times this. Scaling every reward the same
    # way doesn't change the best driving, but keeps the value head's
    # error from crowding out the policy in the shared gradient limit.
    reward_scale: float
    evaluate: bool  # score each checkpoint with the evaluation suite
    description: str = ""
    format: int = TRAINER_FORMAT

    @staticmethod
    def from_dict(data: dict) -> "TrainerSpec":
        if data.get("format") != TRAINER_FORMAT:
            raise TrainerError(
                f"unsupported trainer format {data.get('format')!r}, "
                f"expected {TRAINER_FORMAT}"
            )
        known = set(TrainerSpec.__dataclass_fields__)
        unknown = sorted(set(data) - known)
        if unknown:
            raise TrainerError(f"unknown trainer keys: {', '.join(unknown)}")
        missing = sorted(
            name
            for name, field in TrainerSpec.__dataclass_fields__.items()
            if name not in data and field.default is MISSING
        )
        if missing:
            raise TrainerError(f"missing trainer keys: {', '.join(missing)}")
        spec = TrainerSpec(**data)
        spec.validate()
        return spec

    def to_dict(self) -> dict:
        return asdict(self)

    def validate(self) -> None:
        if self.algorithm not in ALGORITHMS:
            raise TrainerError(
                f"unknown algorithm {self.algorithm!r} "
                f"(known: {', '.join(ALGORITHMS)})"
            )
        if not 0 < self.gamma <= 1:
            raise TrainerError("gamma must be in (0, 1]")
        if not 0 <= self.gae_lambda <= 1:
            raise TrainerError("gae_lambda must be in [0, 1]")
        for name in ("learning_rate", "clip", "max_grad_norm", "reward_scale"):
            if getattr(self, name) <= 0:
                raise TrainerError(f"{name} must be above 0")
        for name in ("entropy", "value_coef"):
            if getattr(self, name) < 0:
                raise TrainerError(f"{name} can't be negative")
        for name in (
            "rollout",
            "minibatch",
            "epochs",
            "total_decisions",
            "checkpoint_every",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 1:
                raise TrainerError(f"{name} must be a whole number, at least 1")
        if not isinstance(self.evaluate, bool):
            raise TrainerError("evaluate must be true or false")
        if self.minibatch > self.rollout:
            raise TrainerError("minibatch can't be larger than rollout")


def load_trainer_spec(name_or_path: str) -> TrainerSpec:
    """A trainer by name (trainers/<name>.json) or by file path."""
    path = Path(name_or_path)
    if path.suffix != ".json":
        path = TRAINERS_DIR / f"{name_or_path}.json"
    if not path.exists():
        raise TrainerError(f"no trainer file {path}")
    return TrainerSpec.from_dict(json.loads(path.read_text()))
