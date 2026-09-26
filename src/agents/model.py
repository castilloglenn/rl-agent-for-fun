"""Model files: an agent's network shape, fixed for its life."""

import json
from dataclasses import dataclass
from pathlib import Path

MODEL_FORMAT = 1
MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
ACTIVATIONS = ("tanh", "relu")
ACTION_SETS = ("canonical12",)


class ModelError(ValueError):
    pass


@dataclass(frozen=True)
class ModelSpec:
    name: str
    hidden: tuple[int, ...]
    activation: str
    observation_version: int
    actions: str
    action_repeat: int
    description: str = ""
    format: int = MODEL_FORMAT

    @staticmethod
    def from_dict(data: dict) -> "ModelSpec":
        if data.get("format") != MODEL_FORMAT:
            raise ModelError(
                f"unsupported model format {data.get('format')!r}, "
                f"expected {MODEL_FORMAT}"
            )
        spec = ModelSpec(
            name=data["name"],
            hidden=tuple(data["hidden"]),
            activation=data["activation"],
            observation_version=data["observation_version"],
            actions=data["actions"],
            action_repeat=data["action_repeat"],
            description=data.get("description", ""),
        )
        spec.validate()
        return spec

    def to_dict(self) -> dict:
        return {
            "format": self.format,
            "name": self.name,
            "description": self.description,
            "hidden": list(self.hidden),
            "activation": self.activation,
            "observation_version": self.observation_version,
            "actions": self.actions,
            "action_repeat": self.action_repeat,
        }

    def validate(self) -> None:
        if not self.hidden or not all(
            isinstance(size, int) and size > 0 for size in self.hidden
        ):
            raise ModelError("hidden must be a list of positive layer sizes")
        if self.activation not in ACTIVATIONS:
            raise ModelError(
                f"unknown activation {self.activation!r} "
                f"(known: {', '.join(ACTIVATIONS)})"
            )
        if self.actions not in ACTION_SETS:
            raise ModelError(
                f"unknown action set {self.actions!r} "
                f"(known: {', '.join(ACTION_SETS)})"
            )
        if not isinstance(self.action_repeat, int) or self.action_repeat < 1:
            raise ModelError("action_repeat must be a whole number, at least 1")


def load_model_spec(name_or_path: str) -> ModelSpec:
    """A model by name (models/<name>.json) or by file path."""
    path = Path(name_or_path)
    if path.suffix != ".json":
        path = MODELS_DIR / f"{name_or_path}.json"
    return ModelSpec.from_dict(json.loads(path.read_text()))
