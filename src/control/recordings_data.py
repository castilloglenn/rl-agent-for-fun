"""The recordings browser's data (roadmap step 6d2): each player's
recorded rounds, from their file names (when, seed, score, how it ended)
and headers (the stage and rules, read once), and which datasets use
each one.

    recordings/<player>/<date>_<time>_seed<N>_score<S>_<ended>.jsonl.gz
    recordings/<player>/kept/...   never removed by the latest-50 limit
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from src.control import runs
from src.control.agents_data import recording_game
from src.utils import named_files

REPO = Path(__file__).resolve().parents[2]
RECORDINGS_DIR = REPO / "recordings"
_NAME = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_(\d{6})_seed(-?\d+)_score(-?\d+)_(.+?)(_\d+)?"
    r"\.jsonl(\.gz)?$"
)
ENDED = {"time": "time", "all_out": "all out", "stopped": "stopped"}


@dataclass
class Recording:
    path: Path
    when: str  # "09-27 02:59:38"
    stamp: str  # "2026-09-27_025938", for sorting
    seed: int
    score: float
    ended: str
    kept: bool
    game: str = ""  # "box / standard, 60 s rounds"
    datasets: list[str] = field(default_factory=list)  # that use it


def parse(path: Path) -> Recording | None:
    """A recording from its file name, or None if it isn't one."""
    match = _NAME.match(path.name)
    if not match:
        return None
    date, clock, seed, score, ended, _, _ = match.groups()
    return Recording(
        path=path,
        when=f"{date[5:]} {clock[:2]}:{clock[2:4]}:{clock[4:]}",
        stamp=f"{date}_{clock}",
        seed=int(seed),
        score=float(score),
        ended=ENDED.get(ended, ended.replace("_", " ")),
        kept=path.parent.name == "kept",
    )


def players(root: Path | None = None) -> list[tuple[str, int]]:
    """(player, recordings) for each folder in recordings/."""
    root = root or RECORDINGS_DIR
    found = []
    for folder in sorted(root.glob("*/")):
        count = sum(1 for _ in folder.glob("*.jsonl*"))
        count += sum(1 for _ in (folder / "kept").glob("*.jsonl*"))
        found.append((folder.name, count))
    return found


def datasets_for(player: str, repo: Path = REPO) -> list[dict]:
    """The dataset files that read this player's recordings."""
    found = []
    for name in named_files.names("datasets", repo):
        data = runs.read_json(named_files.find("datasets", name, repo))
        if data.get("player") == player:
            found.append(data)
    return found


def uses(dataset: dict, recording: Recording) -> bool:
    """By the dataset's rules (include, min_score): what it would read.
    Building the dataset (make dataset) can still skip a round, for
    example one recorded with older physics.
    """
    if dataset.get("include") == "kept" and not recording.kept:
        return False
    return recording.score >= dataset.get("min_score", 0)


def recordings(
    player: str,
    root: Path | None = None,
    repo: Path = REPO,
    sort: str = "newest",
    headers: dict | None = None,
) -> list[Recording]:
    """A player's recordings. `headers` keeps the games already read."""
    folder = (root or RECORDINGS_DIR) / player
    headers = {} if headers is None else headers
    datasets = datasets_for(player, repo)
    found = []
    paths = [*folder.glob("*.jsonl*"), *(folder / "kept").glob("*.jsonl*")]
    for path in paths:
        recording = parse(path)
        if not recording:
            continue
        if path not in headers:
            headers[path] = recording_game(path) or ""
        recording.game = headers[path]
        recording.datasets = [
            d.get("name", "?") for d in datasets if uses(d, recording)
        ]
        found.append(recording)
    if sort == "score":
        found.sort(key=lambda r: (-r.score, r.stamp))
    else:
        found.sort(key=lambda r: r.stamp, reverse=True)
    return found
