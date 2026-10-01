"""Where a replay comes from, for the replay window's SOURCE card: a
training run's episode (which run, which episode, how far training was,
and its mix), a run's episode, or your recording. From the replay's
header and its file's path, nothing else.
"""

import re
from datetime import datetime
from pathlib import Path

_EPISODE = re.compile(r"^ep(\d+)_")
_RUN = re.compile(r"^(\d{4})-(\d\d)-(\d\d)_(\d\d)(\d\d)\d\d_(.+?)(_seed\d+)?$")


def source_rows(header: dict, path: Path | str | None) -> tuple:
    """(label, value) rows: what the SOURCE card shows."""
    path = Path(path) if path else None
    driver = (header.get("slots") or {}).get("1") or {}
    training = driver.get("training")
    rows = []
    if training:
        rows.append(("From", "training"))
        rows.append(("Run", short_run(training.get("run", "?"))))
    elif driver.get("type") == "human":
        kept = path is not None and "kept" in path.parts
        rows.append(("From", "your recording" + (", kept" if kept else "")))
        rows.append(("Player", str(driver.get("player", "?"))))
        rows.append(("Recorded", _local(header.get("recorded_at"))))
        return tuple(rows)
    elif path is not None and path.parent.name == "replays":
        rows.append(("From", "a run"))
        rows.append(("Run", short_run(path.parent.parent.name)))
    else:
        rows.append(("From", path.name if path else "?"))
        return tuple(rows)
    episode = _EPISODE.match(path.name) if path else None
    if episode:
        rows.append(("Episode", f"{int(episode.group(1)):,}"))  # as named
    if training and training.get("decisions") is not None:
        rows.append(("At", f"{_compact(training['decisions'])} decisions"))
    mix = _mix(header)
    if mix:
        rows.append(("Mix", mix))
    return tuple(rows)


def short_run(name: str) -> str:
    """A run folder's name, short: "train-agent_1 · 10-01 12:23"."""
    match = _RUN.match(name)
    if not match:
        return name
    _, month, day, hour, minute, what, _ = match.groups()
    return f"{what} · {month}-{day} {hour}:{minute}"


def _mix(header: dict) -> str | None:
    """The mix the episode was played in (training on a mix records the
    mix's name as the config's stage, and the map as the stage).
    """
    named = (header.get("config") or {}).get("stage")
    stage = header.get("stage")
    played = stage.get("name") if isinstance(stage, dict) else stage
    if named and played and named != played and "/" not in str(named):
        if not str(named).endswith(".json"):
            return str(named)
    return None


def _local(stamp: str | None) -> str:
    if not stamp:
        return "?"
    try:
        when = datetime.fromisoformat(stamp).astimezone()
    except ValueError:
        return stamp
    return when.strftime("%Y-%m-%d %H:%M")


def _compact(value: float) -> str:
    for limit, suffix in ((1e6, "M"), (1e3, "k")):
        if abs(value) >= limit:
            text = f"{value / limit:.1f}".rstrip("0").rstrip(".")
            return text + suffix
    return f"{value:,.0f}"
