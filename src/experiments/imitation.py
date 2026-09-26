"""Imitation (behavioral cloning): an agent learns to drive like a
player's recordings (roadmap step 5b).

    runs/<date>_<time>_imitate-<id>_seed<N>/
      config.json    agent, imitation trainer, dataset and its recordings
      learning.csv   one row per epoch: losses and accuracy, held-out too
      summary.json   rounds, samples, accuracy, the clone's suite scores

The clone is saved as agents/<id>/checkpoints/clone-e<epochs>.pt, and
`make train` can continue it with RL.
"""

import csv
import json
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np
import torch
from ml_collections import ConfigDict

from src.agents.history import record
from src.agents.model import load_model_spec
from src.agents.store import (
    AGENTS_DIR,
    AgentError,
    create_agent,
    load_agent,
    save_checkpoint,
)
from src.agents.trainer import ImitationSpec
from src.experiments.datasets import (
    Dataset,
    DatasetError,
    DatasetSpec,
    Round,
    build_dataset,
)
from src.experiments.evaluation import (
    DEFAULT_SUITE,
    evaluate_checkpoint,
    load_suite,
)
from src.experiments.runner import RUNS_DIR, _new_folder
from src.utils.version import code_version

LEARNING_COLUMNS = (
    "epoch",
    "seconds",
    "train_loss",
    "train_accuracy",
    "held_out_loss",
    "held_out_accuracy",
    "value_loss",
)


@dataclass(frozen=True)
class EpochReport:
    epoch: int
    epochs: int
    train_accuracy: float
    held_out_accuracy: float | None
    seconds: float


@dataclass(frozen=True)
class ImitationSummary:
    folder: Path
    agent: str
    checkpoint: str
    rounds: int
    held_out_rounds: int
    samples: int
    train_accuracy: float
    held_out_accuracy: float | None
    player_mean_score: float
    evaluation: dict | None
    seconds: float


def imitate(
    agent: str,
    trainer: ImitationSpec,
    dataset: DatasetSpec,
    config: ConfigDict,
    runs_dir: Path | None = None,
    agents_root: Path | None = None,
    recordings_root: Path | None = None,
    on_epoch: Callable[[EpochReport], None] | None = None,
    suite: str = DEFAULT_SUITE,
) -> ImitationSummary:
    """Clones the dataset's driving into an agent (created with the small
    model if it doesn't exist yet), starting from its newest checkpoint.
    """
    root = agents_root or AGENTS_DIR
    try:
        loaded = load_agent(agent, root=root)
    except AgentError:
        create_agent(agent, load_model_spec("small"), root=root)
        loaded = load_agent(agent, root=root)
    data = build_dataset(dataset, loaded.spec.action_repeat, recordings_root)
    if not data.rounds:
        raise DatasetError(
            f"dataset {dataset.name!r} has no usable rounds for player "
            f"{dataset.player!r}: record some with make maze_car"
        )
    started = time.perf_counter()
    train, held_out = _split(data.rounds, trainer)
    folder = _new_folder(
        runs_dir or RUNS_DIR, f"imitate-{loaded.agent_id}", trainer.seed
    )
    _write_config(folder, loaded, trainer, data, held_out)
    record(
        loaded.folder,
        "phase_started",
        kind="imitation",
        run=folder.name,
        trainer=trainer.name,
        reward="-",
        stage="/".join(sorted({r.stage for r in data.rounds})),
        rules="/".join(sorted({r.rules for r in data.rounds})),
        dataset=dataset.name,
        player=dataset.player,
        rounds=len(data.rounds),
        samples=data.samples,
        start_checkpoint=loaded.checkpoint,
        start_decisions=loaded.decisions,
    )

    network = loaded.network
    optimizer = torch.optim.Adam(network.parameters(), lr=trainer.learning_rate)
    generator = torch.Generator().manual_seed(trainer.seed)
    x, y, returns = _tensors(train, trainer)
    test = _tensors(held_out, trainer) if held_out else None
    rows = []
    with open(folder / "learning.csv", "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(LEARNING_COLUMNS)
        for epoch in range(1, trainer.epochs + 1):
            network.train()
            order = torch.randperm(len(y), generator=generator)
            for start in range(0, len(y), trainer.minibatch):
                index = order[start : start + trainer.minibatch]
                logits, values = network(x[index])
                loss = torch.nn.functional.cross_entropy(logits, y[index])
                if trainer.value:
                    loss = loss + 0.5 * (values - returns[index]).pow(2).mean()
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
            network.eval()
            train_loss, train_accuracy, _ = _measure(network, x, y, returns)
            held = _measure(network, *test) if test else (None, None, None)
            seconds = time.perf_counter() - started
            row = [
                epoch,
                round(seconds, 3),
                round(train_loss, 6),
                round(train_accuracy, 6),
                *("" if v is None else round(v, 6) for v in held),
            ]
            writer.writerow(row)
            file.flush()
            rows.append(row)
            if on_epoch:
                on_epoch(
                    EpochReport(
                        epoch, trainer.epochs, train_accuracy, held[1], seconds
                    )
                )

    name = _checkpoint_name(loaded.folder, trainer.epochs)
    save_checkpoint(
        loaded.folder,
        name,
        network,
        loaded.spec,
        {
            "decisions": loaded.decisions,
            "run": folder.name,
            "trainer": trainer.name,
            "dataset": dataset.name,
        },
    )
    record(
        loaded.folder,
        "checkpoint_saved",
        run=folder.name,
        checkpoint=name,
        decisions=loaded.decisions,
    )
    evaluation = None
    if trainer.evaluate:
        evaluation = evaluate_checkpoint(
            loaded.folder, name, load_suite(suite), config
        )
    seconds = round(time.perf_counter() - started, 3)
    summary = ImitationSummary(
        folder=folder,
        agent=loaded.agent_id,
        checkpoint=name,
        rounds=len(data.rounds),
        held_out_rounds=len(held_out),
        samples=data.samples,
        train_accuracy=rows[-1][3],
        held_out_accuracy=rows[-1][5] if held_out else None,
        player_mean_score=data.mean_score,
        evaluation=evaluation,
        seconds=seconds,
    )
    (folder / "summary.json").write_text(
        json.dumps({**asdict(summary), "folder": str(folder)}, indent=2)
        + "\n"
    )
    record(
        loaded.folder,
        "phase_ended",
        run=folder.name,
        interrupted=False,
        decisions=loaded.decisions,
        episodes=0,
        seconds=seconds,
        accuracy=summary.held_out_accuracy or summary.train_accuracy,
    )
    return summary


def _split(
    rounds: list[Round], trainer: ImitationSpec
) -> tuple[list[Round], list[Round]]:
    """Holds out whole rounds (not single samples), so the check isn't
    flattered by near-copies of training samples.
    """
    order = list(range(len(rounds)))
    random.Random(trainer.seed).shuffle(order)
    count = round(len(rounds) * trainer.validation)
    if trainer.validation and len(rounds) >= 2:
        count = max(count, 1)
    count = min(count, len(rounds) - 1)
    held = {order[i] for i in range(count)}
    return (
        [r for i, r in enumerate(rounds) if i not in held],
        [r for i, r in enumerate(rounds) if i in held],
    )


def _tensors(rounds: list[Round], trainer: ImitationSpec):
    x = torch.as_tensor(np.concatenate([r.observations for r in rounds]))
    y = torch.as_tensor(np.concatenate([r.actions for r in rounds]))
    returns = torch.as_tensor(
        np.concatenate([_returns(r.rewards, trainer) for r in rounds])
    )
    return x, y, returns


def _returns(rewards: np.ndarray, trainer: ImitationSpec) -> np.ndarray:
    """Discounted rewards to the round's end, scaled like the RL trainer."""
    result = np.zeros(len(rewards), dtype=np.float32)
    running = 0.0
    for t in reversed(range(len(rewards))):
        running = rewards[t] * trainer.reward_scale + trainer.gamma * running
        result[t] = running
    return result


def _measure(network, x, y, returns) -> tuple[float, float, float]:
    """(policy loss, accuracy, value loss) on a whole set."""
    with torch.no_grad():
        logits, values = network(x)
        loss = float(torch.nn.functional.cross_entropy(logits, y))
        accuracy = float((logits.argmax(-1) == y).float().mean())
        value_loss = float(0.5 * (values - returns).pow(2).mean())
    return loss, accuracy, value_loss


def _checkpoint_name(folder: Path, epochs: int) -> str:
    base = name = f"clone-e{epochs}"
    suffix = 1
    while (folder / "checkpoints" / f"{name}.pt").exists():
        suffix += 1
        name = f"{base}_{suffix}"
    return name


def _write_config(folder, loaded, trainer, data: Dataset, held_out) -> None:
    held = {r.path.name for r in held_out}
    config = {
        "format": 1,
        "kind": "imitation",
        "name": folder.name,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "code": code_version(),
        "driver": {"type": "agent", "id": loaded.agent_id},
        "agent": {
            "id": loaded.agent_id,
            "model": loaded.spec.to_dict(),
            "start_checkpoint": loaded.checkpoint,
            "start_decisions": loaded.decisions,
        },
        "trainer": trainer.to_dict(),
        # Names only, so run listings work: the rounds have their own.
        "stage": {"name": "/".join(sorted({r.stage for r in data.rounds}))},
        "rules": {"name": "/".join(sorted({r.rules for r in data.rounds}))},
        "reward": {"name": "-"},
        "dataset": data.spec.to_dict(),
        "recordings": [
            {
                "file": r.path.name,
                "score": r.score,
                "ended_by": r.ended_by,
                "samples": len(r.actions),
                "held_out": r.path.name in held,
            }
            for r in data.rounds
        ],
        "skipped": [
            {"file": path.name, "why": why} for path, why in data.skipped
        ],
    }
    (folder / "config.json").write_text(json.dumps(config, indent=2) + "\n")
