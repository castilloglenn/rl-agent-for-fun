"""What each command parameter can be, from the files on disk
(roadmap step 6a). The control center offers these in a dropdown, so a
typo can't happen. Parameters that name something new (a new agent, a
player) are typed instead.
"""

import json
from pathlib import Path

from src.utils import named_files

REPO = Path(__file__).resolve().parents[2]
BASELINES = ("heuristic", "random")
# Commands whose AGENT is a new name, not an existing agent.
NEW_AGENT = ("new_agent", "imitate")
TYPED = ("PLAYER", "SECONDS", "FPS", "EPISODES")


class Choice(str):
    """A dropdown value that shows another text: "ruins · yours" picks
    "ruins". Everything else sees the plain name.
    """

    label: str

    def __new__(cls, value: str, label: str) -> "Choice":
        choice = super().__new__(cls, value)
        choice.label = label
        return choice


YOURS = "yours"  # the tag of a file of yours in a dropdown (7d1b)


def named(kind: str, root: Path = REPO) -> list[str]:
    """A kind's names for a dropdown: the built-ins, then yours, tagged."""
    return [
        name
        if named_files.is_built_in(kind, name, root)
        else Choice(name, f"{name} · {YOURS}")
        for name in named_files.ordered(kind, root)
    ]


def _names(folder: str) -> list[str]:
    return named(folder)


def agent_label(folder: Path) -> str:
    """An agent as shown: "Reverse Guy · agent-1" with a nickname of
    yours (7c10), else its id.
    """
    try:
        nickname = json.loads((folder / "profile.json").read_text()).get(
            "nickname"
        )
    except (OSError, ValueError):
        nickname = None
    return f"{nickname} · {folder.name}" if nickname else folder.name


def agents(folder: Path | None = None) -> list[str]:
    """Every agent's id, shown with its nickname if it has one."""
    folder = folder or REPO / "agents"
    found = sorted(
        p for p in folder.glob("*/") if (p / "model.json").exists()
    )
    return [Choice(p.name, agent_label(p)) for p in found]


def runs() -> list[str]:
    """Newest first, since that's usually the one you want."""
    folder = REPO / "runs"
    return sorted(
        (p.name for p in folder.glob("*/") if (p / "config.json").exists()),
        reverse=True,
    )


def recordings(limit: int = 30) -> list[str]:
    """The newest recordings, as paths from the repo root."""
    files = sorted(
        (REPO / "recordings").glob("**/*.jsonl*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return [str(p.relative_to(REPO)) for p in files[:limit]]


def test_files() -> list[str]:
    return sorted(
        str(p.relative_to(REPO)) for p in (REPO / "tests").glob("test_*.py")
    )


def options(command: str, param: str) -> list[str] | None:
    """The choices for a parameter, or None if it's typed freely."""
    if param in TYPED or (param == "AGENT" and command in NEW_AGENT):
        return None
    if param == "AGENT":
        return agents()
    if param == "DRIVER":
        # Runs are headless, so the keyboard only drives in the window.
        drivers = ["keyboard"] if command.startswith("maze_car") else []
        return [*drivers, *BASELINES, *(f"agent:{a}" for a in agents())]
    if param in ("RULES", "REWARD", "STAGE"):
        folder = {"RULES": "rules", "REWARD": "rewards", "STAGE": "stages"}
        return _names(folder[param])
    if param == "RUN":
        return runs()
    if param == "FILE":
        return test_files() if command == "test_file" else recordings()
    return None
