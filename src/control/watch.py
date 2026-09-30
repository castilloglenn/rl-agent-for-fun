"""Data in sync across the control center (roadmap 7c7, decision 044).

One watcher looks at every data folder's modification time. A folder's
time changes when anything in it is added, removed, or renamed, whoever
did it: a tab (a delete, a restore, a save), a job (a new run, agent, or
checkpoint), a terminal, or a game window. So the window asks `changed()`
every half second and tells each tab which kinds of data changed; the tab
rebuilds only what they touch. About 20 `stat` calls: well under a
millisecond, and nothing is read unless something changed.

Edits inside an existing file (an agent's scores) don't change a folder's
time: each tab's own timer re-reads those.
"""

import os
from pathlib import Path

from src.utils import named_files

REPO = Path(__file__).resolve().parents[2]
NAMED = named_files.KINDS  # stages, rules, rewards, ... (and user/ twins)
# The kinds a tab can care about.
KINDS = ("agents", "checkpoints", "runs", "recordings", "trash", *NAMED)


class DataWatch:
    def __init__(
        self,
        root: Path | None = None,
        runs_dir: Path | None = None,
        agents_dir: Path | None = None,
    ) -> None:
        """`root`: the repo (tests use a copy). `runs_dir`, `agents_dir`:
        where runs and agents live, if not in `root`.
        """
        self.root = Path(root or REPO)
        self.runs_dir = Path(runs_dir or self.root / "runs")
        self.agents_dir = Path(agents_dir or self.root / "agents")
        self._last: dict[str, tuple] | None = None

    def _folders(self) -> dict[str, list[Path]]:
        """Each kind's folders. Checkpoints and recordings live one level
        down (an agent's checkpoints/, a player's folder and its kept/).
        """
        recordings = self.root / "recordings"
        players = _subfolders(recordings)
        folders = {
            "agents": [self.agents_dir],
            "checkpoints": [
                agent / "checkpoints" for agent in _subfolders(self.agents_dir)
            ],
            "runs": [self.runs_dir],
            "recordings": [
                recordings,
                *players,
                *(player / "kept" for player in players),
            ],
            "trash": [self.root / "trash"],
        }
        for kind in NAMED:
            folders[kind] = [
                named_files.built_in_folder(kind, self.root),
                named_files.user_folder(kind, self.root),
            ]
        return folders

    def _times(self) -> dict[str, tuple]:
        return {
            kind: tuple((str(p), _mtime(p)) for p in paths)
            for kind, paths in self._folders().items()
        }

    def changed(self) -> set[str]:
        """The kinds of data added, removed, or renamed since the last
        call (nothing on the first, which only looks).
        """
        now = self._times()
        before, self._last = self._last, now
        if before is None:
            return set()
        return {kind for kind in now if now[kind] != before.get(kind)}


def _mtime(path: Path) -> int | None:
    try:
        return os.stat(path).st_mtime_ns
    except OSError:
        return None  # not there (yet): its appearing is a change


def _subfolders(path: Path) -> list[Path]:
    try:
        return sorted(p for p in path.iterdir() if p.is_dir())
    except OSError:
        return []
