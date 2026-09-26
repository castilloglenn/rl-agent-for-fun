"""Listing run folders, and finding their best replay."""

import json
from pathlib import Path

from src.experiments.runner import RUNS_DIR


def list_runs(runs_dir: Path | None = None) -> list[dict]:
    """One row per run folder (newest first), from config and summary."""
    rows = []
    for folder in sorted((runs_dir or RUNS_DIR).glob("*/"), reverse=True):
        config_file = folder / "config.json"
        if not config_file.exists():
            continue
        config = json.loads(config_file.read_text())
        summary_file = folder / "summary.json"
        summary = {}
        if summary_file.exists():
            summary = json.loads(summary_file.read_text())
        rows.append(
            {
                "folder": folder.name,
                "driver": config["driver"].get("id")
                or config["driver"].get("player"),
                "stage": config["stage"]["name"],
                "rules": config["rules"]["name"],
                "reward": config["reward"]["name"],
                "episodes": summary.get("episodes", "?"),
                "mean_score": summary.get("mean_score"),
                "best_score": summary.get("best_score"),
                "survival": summary.get("survival_rate"),
                "status": (
                    "running or crashed"
                    if not summary
                    else "interrupted"
                    if summary.get("interrupted")
                    else "done"
                ),
            }
        )
    return rows


def format_runs(rows: list[dict]) -> str:
    if not rows:
        return "No runs yet. Start one with: make run_heuristic"
    lines = [
        f"{'run':44s} {'driver':10s} {'stage':6s} {'rules':9s} "
        f"{'reward':11s} {'eps':>4s} {'mean':>8s} {'best':>8s} {'surv':>5s}"
    ]
    for row in rows:
        mean = row["mean_score"]
        best = row["best_score"]
        survival = row["survival"]
        lines.append(
            f"{row['folder'][:44]:44s} {str(row['driver'])[:10]:10s} "
            f"{row['stage'][:6]:6s} {row['rules'][:9]:9s} "
            f"{row['reward'][:11]:11s} {str(row['episodes']):>4s} "
            f"{'' if mean is None else f'{mean:,.0f}':>8s} "
            f"{'' if best is None else f'{best:,.0f}':>8s} "
            f"{'' if survival is None else f'{survival:.0%}':>5s}"
            + ("" if row["status"] == "done" else f"  ({row['status']})")
        )
    return "\n".join(lines)


def best_replay(run: str | Path, runs_dir: Path | None = None) -> Path:
    """The replay with the highest score in a run folder (by path, or by
    folder name inside runs/).
    """
    folder = Path(run)
    if not folder.exists():
        folder = (runs_dir or RUNS_DIR) / run
    replays = list((folder / "replays").glob("*.jsonl*"))
    if not replays:
        raise FileNotFoundError(f"no replays in {folder}")
    return max(replays, key=_replay_score)


def _replay_score(path: Path) -> float:
    # Names look like ep0012_score2456.jsonl.gz
    return float(path.name.split("_score")[1].split(".")[0])
