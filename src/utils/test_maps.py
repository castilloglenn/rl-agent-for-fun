"""Which skills a map is the test for (roadmap 7d3b, decision 043):
training on a test map makes its skill's score measure memory, not skill,
so the Training tab and `make train` warn. The box never warns: it's the
default map to train on, and its skills (Braking, Open field) are the
ones every agent trains on anyway.

No torch here: the control center reads it too.
"""

from pathlib import Path

from src.utils import mixes, named_files
from src.utils import skills as suite_skills

SUITE = "skills"  # the default suite (src/experiments/evaluation.py)
TRAINING_MAP = "box"  # the default map to train on: never a warning


def _scenarios(root: Path) -> list[dict]:
    return suite_skills.scenarios(SUITE, root)


def skills(root: Path = named_files.REPO) -> list[tuple[str, str]]:
    """The default suite's skills: (name, label), in the suite's order."""
    return [(s["name"], s.get("label") or s["name"]) for s in _scenarios(root)]


def skills_on(stage: str, root: Path = named_files.REPO) -> list[str]:
    """The default suite's skills played on `stage` (their labels)."""
    return [
        s.get("label") or s["name"]
        for s in _scenarios(root)
        if s.get("stage") == stage
    ]


def warning(stage: str, root: Path = named_files.REPO) -> str | None:
    """What to say before training on `stage`, a stage or a mix (7d5a:
    every map in it). None: nothing.
    """
    from src.utils import curricula

    kind = "mix"
    try:
        if curricula.is_curriculum(stage, root):  # 7f5: every level's
            names = curricula.load_curriculum(stage, root).all_maps(root)
            kind = "curriculum"
        else:
            names = mixes.stages_of(stage, root)
    except (mixes.MixError, curricula.CurriculumError):
        return None  # a broken mix or curriculum: training reports it
    found = [_warning(name, root) for name in names]
    found = [text for text in found if text]
    if not found:
        return None
    if names == [stage]:
        return found[0]
    return f"{kind} {stage}: " + "; ".join(found)


def _warning(stage: str, root: Path) -> str | None:
    if stage == TRAINING_MAP:
        return None
    skills = skills_on(stage, root)
    if not skills:
        return None
    return (
        f"{stage} is a test map: its {' and '.join(skills)} score would "
        "measure memory, not skill"
    )
