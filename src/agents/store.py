"""Stored agents: agents/<id>/ with its model and checkpoints.

    agents/<id>/model.json          the agent's model (fixed for life)
    agents/<id>/checkpoints/*.pt    weights, with the model they fit

Roadmap 5a5 adds the agent's profile and history next to these.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

import torch

from src.agents.model import ModelSpec
from src.agents.network import PolicyNetwork
from src.drivers.actions import CANONICAL_ACTIONS, CANONICAL_NAMES
from src.sim.observation import OBSERVATION_NAMES, OBSERVATION_VERSION

AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"
CHECKPOINT_FORMAT = 1
_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class AgentError(ValueError):
    pass


@dataclass
class LoadedAgent:
    agent_id: str
    folder: Path
    spec: ModelSpec
    network: PolicyNetwork
    checkpoint: str  # checkpoint name, e.g. "initial"
    decisions: int = 0  # decisions trained on so far, over all phases


def new_network(spec: ModelSpec) -> PolicyNetwork:
    return PolicyNetwork(spec, len(OBSERVATION_NAMES), len(CANONICAL_ACTIONS))


def create_agent(
    agent_id: str, spec: ModelSpec, seed: int = 0, root: Path | None = None
) -> Path:
    """A new, untrained agent: its model plus an "initial" checkpoint with
    seeded random weights.
    """
    if not _ID.match(agent_id):
        raise AgentError(
            f"agent id {agent_id!r}: use letters, digits, - and _ only"
        )
    folder = (root or AGENTS_DIR) / agent_id
    if folder.exists():
        raise AgentError(f"agent {agent_id!r} already exists: {folder}")
    _check_compatible(spec)
    (folder / "checkpoints").mkdir(parents=True)
    (folder / "model.json").write_text(
        json.dumps(spec.to_dict(), indent=2) + "\n"
    )
    with torch.random.fork_rng():  # seeded, without touching global state
        torch.manual_seed(seed)
        network = new_network(spec)
    save_checkpoint(folder, "initial", network, spec, {"seed": seed})
    return folder


def save_checkpoint(
    folder: Path,
    name: str,
    network: PolicyNetwork,
    spec: ModelSpec,
    extra: dict | None = None,
) -> Path:
    path = folder / "checkpoints" / f"{name}.pt"
    torch.save(
        {
            "format": CHECKPOINT_FORMAT,
            "model": spec.to_dict(),
            "action_names": list(CANONICAL_NAMES),
            "weights": network.state_dict(),
            **(extra or {}),
        },
        path,
    )
    return path


def load_agent(
    agent: str | Path, checkpoint: str | None = None, root: Path | None = None
) -> LoadedAgent:
    """An agent by id (agents/<id>) or folder path, at a checkpoint
    (default: the newest).
    """
    folder = Path(agent)
    if not (folder / "model.json").exists():
        folder = (root or AGENTS_DIR) / str(agent)
    if not (folder / "model.json").exists():
        raise AgentError(f"no agent at {folder}")
    spec = ModelSpec.from_dict(json.loads((folder / "model.json").read_text()))
    _check_compatible(spec)

    checkpoints = folder / "checkpoints"
    if checkpoint is None:
        files = sorted(
            checkpoints.glob("*.pt"), key=lambda p: p.stat().st_mtime_ns
        )
        if not files:
            raise AgentError(f"agent {folder.name!r} has no checkpoints")
        path = files[-1]
    else:
        path = checkpoints / f"{checkpoint}.pt"
    if not path.exists():
        raise AgentError(
            f"agent {folder.name!r} has no checkpoint {path.stem!r}"
        )
    data = torch.load(path, weights_only=True)
    if data.get("format") != CHECKPOINT_FORMAT:
        raise AgentError(f"unsupported checkpoint format in {path}")
    # Safety rule (decision 014): weights only fit the model they were
    # trained with.
    if data["model"] != spec.to_dict():
        raise AgentError(
            f"{path.name} was made for another model than {folder.name}'s"
        )
    if data["action_names"] != list(CANONICAL_NAMES):
        raise AgentError(f"{path.name} uses another action set")

    network = new_network(spec)
    network.load_state_dict(data["weights"])
    network.eval()
    return LoadedAgent(
        folder.name,
        folder,
        spec,
        network,
        path.stem,
        int(data.get("decisions", 0)),
    )


def _check_compatible(spec: ModelSpec) -> None:
    if spec.observation_version != OBSERVATION_VERSION:
        raise AgentError(
            f"model {spec.name!r} expects observation version "
            f"{spec.observation_version}, but the game now has "
            f"{OBSERVATION_VERSION}"
        )
