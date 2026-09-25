import subprocess
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


@lru_cache
def code_version() -> str:
    """The git commit this code runs from, e.g. "a1b2c3d", or
    "a1b2c3d-dirty" with uncommitted changes. "unknown" without git.
    Replays and runs record it.
    """
    try:
        commit = _git("rev-parse", "--short", "HEAD")
        dirty = _git("status", "--porcelain", "--untracked-files=no")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"{commit}-dirty" if dirty else commit


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    return result.stdout.strip()
