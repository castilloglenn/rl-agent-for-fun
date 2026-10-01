"""Map mixes (roadmap 7d5a): a named file listing stages, so one training
phase plays several maps in turn (episode i plays map i mod n). The
standard cure for forgetting: the agent never stops practicing any of
them. No torch: the control center reads it too.

    mixes/<name>.json  {"format": 1, "name": "basics",
                        "stages": ["box", "pillars", "s_curve", "arena"]}

A mix goes wherever a stage name goes for training. A stage of the same
name wins, so a name always means one thing.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from src.utils import named_files

MIX_FORMAT = 1
KIND = "mixes"


class MixError(ValueError):
    pass


@dataclass(frozen=True)
class Mix:
    name: str
    stages: tuple[str, ...]

    @staticmethod
    def from_dict(data: dict) -> "Mix":
        if data.get("format") != MIX_FORMAT:
            raise MixError(
                f"unsupported mix format {data.get('format')!r}, "
                f"expected {MIX_FORMAT}"
            )
        stages = data.get("stages")
        if not isinstance(stages, list) or not stages:
            raise MixError("a mix needs a list of stages")
        if not all(isinstance(s, str) and s for s in stages):
            raise MixError("each stage in a mix is a stage's name")
        return Mix(data["name"], tuple(stages))

    def check(self, root: Path = named_files.REPO) -> None:
        """Every stage exists (MixError names the first that doesn't)."""
        known = set(named_files.names("stages", root))
        for stage in self.stages:
            if stage not in known:
                raise MixError(f"mix {self.name!r}: no stage {stage!r}")


def is_mix(name: str, root: Path = named_files.REPO) -> bool:
    """`name` is a mix (and not a stage, which wins)."""
    names = named_files.names
    return name in names(KIND, root) and name not in names("stages", root)


def load_mix(name: str, root: Path = named_files.REPO) -> Mix:
    """The mix named `name` (built-in, else yours), its stages checked."""
    try:
        data = json.loads(named_files.find(KIND, name, root).read_text())
    except FileNotFoundError as error:
        raise MixError(str(error))
    mix = Mix.from_dict(data)
    mix.check(root)
    return mix


def stages_of(name: str, root: Path = named_files.REPO) -> list[str]:
    """The stages a training on `name` plays: a mix's, or the stage."""
    return list(load_mix(name, root).stages) if is_mix(name, root) else [name]
