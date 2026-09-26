"""Listing agents and printing an agent's digest (roadmap step 5a6)."""

import json
from pathlib import Path

from src.agents.history import read_profile
from src.agents.store import AGENTS_DIR, AgentError, load_agent
from src.experiments.evaluation import (
    DEFAULT_SUITE,
    load_suite,
    read_results,
)

SPARKS = "▁▂▃▄▅▆▇█"


def list_agents(root: Path | None = None) -> list[dict]:
    """One profile per agent folder, newest update first."""
    root = root or AGENTS_DIR
    profiles = [
        read_profile(folder)
        for folder in sorted(root.glob("*/"))
        if (folder / "model.json").exists()
    ]
    return sorted(profiles, key=lambda p: p["updated"] or "", reverse=True)


def format_agents(profiles: list[dict]) -> str:
    if not profiles:
        return "No agents yet. Create one with: make new_agent AGENT=rookie"
    lines = [
        f"{'agent':16s} {'model':7s} {'decisions':>10s} {'best':>9s} "
        f"{'score':>7s} {'surv':>5s} {'milestone':9s} {'updated':16s}"
    ]
    for p in profiles:
        best = p["best"]
        lines.append(
            f"{p['id'][:16]:16s} {p['model']['name'][:7]:7s} "
            f"{p['decisions']:>10,} {p['checkpoints']['best'] or '':>9s} "
            f"{'' if not best else f'{best['score_mean']:,.0f}':>7s} "
            f"{'' if not best else f'{best['survival']:.0%}':>5s} "
            f"{'yes' if p['milestone'] else '':9s} "
            f"{(p['updated'] or '')[:16].replace('T', ' '):16s}"
        )
    return "\n".join(lines)


def agent_summary(agent: str, root: Path | None = None) -> str:
    """A compact digest: lineage, best scores next to the heuristic, the
    score trend over scored checkpoints, totals, and the milestone.
    """
    folder = load_agent(agent, "initial", root=root).folder
    profile = read_profile(folder)
    suite = load_suite(DEFAULT_SUITE)
    rows = read_results(folder, suite)
    model = profile["model"]
    shape = "x".join(str(size) for size in model["hidden"])
    training = profile["training"]
    lines = [
        f"{profile['id']}  (model {model['name']}: {shape} "
        f"{model['activation']})",
        f"  {profile['decisions']:,} decisions, "
        f"{_count(training['phases'], 'training phase')}, "
        f"{_count(training['episodes'], 'episode')}, "
        f"{training['seconds'] / 60:,.1f} min training, "
        f"{_count(profile['checkpoints']['count'], 'checkpoint')}",
    ]
    if profile["branched_from"]:
        source = profile["branched_from"]
        lines.append(
            f"  branched from {source['agent']}@{source['checkpoint']}"
        )
    if profile["phases"]:
        lines.append("  phases:")
    for i, phase in enumerate(profile["phases"], 1):
        if phase["kind"] == "imitation":
            data = phase["dataset"]
            accuracy = phase.get("accuracy")
            lines.append(
                f"    {i}. {phase['run']}: cloned from {data['player']} "
                f"({data['rounds']} rounds, {data['samples']:,} samples, "
                f"dataset {data['dataset']})"
                + (f", accuracy {accuracy:.0%}" if accuracy else "")
                + f" ({phase['status']})"
            )
            continue
        lines.append(
            f"    {i}. {phase['run']}: trainer {phase['trainer']}, "
            f"reward {phase['reward']}, {phase['stage']}/{phase['rules']}, "
            f"{phase['start_decisions']:,} -> {phase['end_decisions']:,} "
            f"({phase['status']})"
        )
    best = profile["best"]
    heuristic = _heuristic_score(folder, suite)
    if best:
        versus = (
            f"  (heuristic {heuristic:,.0f})" if heuristic is not None else ""
        )
        lines.append(
            f"  best: {profile['checkpoints']['best']} on {best['suite']}: "
            f"score {best['score_mean']:,.0f} (worst "
            f"{best['score_min']:,.0f}), survival {best['survival']:.0%}, "
            f"wrecks {best['wreck_rate']:.0%}, "
            f"braking {best['braking']:.0%}{versus}"
        )
    else:
        lines.append(f"  not scored yet: make eval AGENT={profile['id']}")
    if len(rows) > 1:
        scores = [r["score_mean"] for r in rows]
        lines.append(
            f"  trend ({len(rows)} scored checkpoints): {sparkline(scores)}  "
            f"{scores[0]:,.0f} -> {scores[-1]:,.0f}"
        )
    milestone = profile["milestone"]
    if milestone:
        lines.append(
            f"  milestone: {milestone['name']}, reached at "
            f"{milestone['checkpoint']} ({milestone['score_mean']:,.0f} vs "
            f"heuristic {milestone['heuristic_score']:,.0f}, wrecks "
            f"{milestone['wreck_rate']:.0%})"
        )
    else:
        lines.append(
            "  milestone: not yet (the best checkpoint must beat the "
            "heuristic's mean score and wreck in under half the rounds)"
        )
    return "\n".join(lines)


def _count(n: int, noun: str) -> str:
    return f"{n:,} {noun}" + ("" if n == 1 else "s")


def sparkline(values: list[float]) -> str:
    low, high = min(values), max(values)
    span = (high - low) or 1.0
    return "".join(
        SPARKS[round((v - low) / span * (len(SPARKS) - 1))] for v in values
    )


def _heuristic_score(folder: Path, suite) -> float | None:
    """From the baseline cache (written when checkpoints are scored)."""
    path = folder.parent / "baselines" / f"{suite.label}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())["scores"]["heuristic"]["score_mean"]


__all__ = ["AgentError", "agent_summary", "format_agents", "list_agents"]
