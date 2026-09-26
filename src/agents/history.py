"""An agent's history and profile (roadmap step 5a6).

    agents/<id>/history.jsonl   one line per event, appended, never rewritten
    agents/<id>/profile.json    a ~2 KB digest, rewritten after each event

Read the profile first, and the history only when needed. A Ctrl+C can
repeat an event after resume: readers keep the latest of each.
"""

import csv
import json
from datetime import datetime
from pathlib import Path

HISTORY_FILE = "history.jsonl"
PROFILE_FILE = "profile.json"
BEST_FILE = "evaluations/best.json"  # the best checkpoint (5a5)


def record(folder: Path, event: str, **data) -> dict:
    """Appends an event to the agent's history, and rewrites its
    profile.
    """
    line = {
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "event": event,
        **data,
    }
    with open(Path(folder) / HISTORY_FILE, "a") as file:
        file.write(json.dumps(line) + "\n")
    write_profile(folder)
    return line


def read_history(folder: Path) -> list[dict]:
    path = Path(folder) / HISTORY_FILE
    if not path.exists():
        return []
    lines = path.read_text().splitlines()
    return [json.loads(line) for line in lines if line]


def write_profile(folder: Path) -> dict:
    profile = build_profile(folder)
    text = json.dumps(profile, indent=2) + "\n"
    (Path(folder) / PROFILE_FILE).write_text(text)
    return profile


def read_profile(folder: Path) -> dict:
    path = Path(folder) / PROFILE_FILE
    if not path.exists():
        return build_profile(folder)
    return json.loads(path.read_text())


def build_profile(folder: Path) -> dict:
    """The digest, from the history and the files on disk."""
    folder = Path(folder)
    model = json.loads((folder / "model.json").read_text())
    history = read_history(folder)
    created = next((e for e in history if e["event"] == "created"), None)

    phases: dict[str, dict] = {}  # by run, in start order
    milestone = None
    for event in history:
        kind, run = event["event"], event.get("run")
        if kind == "phase_started":
            phases[run] = {
                "kind": event.get("kind", "rl"),
                "run": run,
                "trainer": event["trainer"],
                "reward": event["reward"],
                "stage": event["stage"],
                "rules": event["rules"],
                "start_decisions": event["start_decisions"],
                "end_decisions": event["start_decisions"],
                "episodes": 0,
                "seconds": 0.0,
                "status": "running or stopped",
            }
            if event.get("kind") == "imitation":
                phases[run]["dataset"] = {
                    k: event[k]
                    for k in ("dataset", "player", "rounds", "samples")
                }
        elif kind == "checkpoint_saved" and run in phases:
            phases[run]["end_decisions"] = event["decisions"]
        elif kind == "phase_ended" and run in phases:
            phases[run].update(
                end_decisions=event["decisions"],
                episodes=event["episodes"],
                seconds=event["seconds"],
                status="stopped" if event["interrupted"] else "done",
            )
            if "accuracy" in event:
                phases[run]["accuracy"] = event["accuracy"]
        elif kind == "milestone" and milestone is None:
            milestone = {k: v for k, v in event.items() if k != "event"}

    checkpoints = sorted(
        (folder / "checkpoints").glob("*.pt"),
        key=lambda p: p.stat().st_mtime_ns,
    )
    best, scores = _best_scores(folder)
    return {
        "id": folder.name,
        "model": {k: model[k] for k in ("name", "hidden", "activation")},
        "observation_version": model["observation_version"],
        "created": created["time"] if created else None,
        "branched_from": created.get("branched_from") if created else None,
        "decisions": max(
            [p["end_decisions"] for p in phases.values()]
            + [created.get("decisions", 0) if created else 0]
        ),
        "training": {
            "phases": len(phases),
            "episodes": sum(p["episodes"] for p in phases.values()),
            "seconds": round(sum(p["seconds"] for p in phases.values()), 1),
        },
        "phases": list(phases.values()),
        "checkpoints": {
            "count": len(checkpoints),
            "newest": checkpoints[-1].stem if checkpoints else None,
            "best": best,
        },
        "best": scores,
        "milestone": milestone,
        "updated": history[-1]["time"] if history else None,
    }


def _best_scores(folder: Path) -> tuple[str | None, dict | None]:
    path = folder / BEST_FILE
    if not path.exists():
        return None, None
    best = json.loads(path.read_text())
    results = folder / "evaluations" / f"{best['suite']}.csv"
    if not results.exists():
        return best["checkpoint"], None
    with open(results, newline="") as file:
        for row in csv.DictReader(file):
            if row["checkpoint"] == best["checkpoint"]:
                scores = {
                    k: float(v) for k, v in row.items() if k != "checkpoint"
                }
                return best["checkpoint"], {"suite": best["suite"], **scores}
    return best["checkpoint"], None
