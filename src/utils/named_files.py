"""Built-in named files and yours (roadmap 7d1, decision 039).

A named file is a JSON file found by its name: a stage, rules, a reward
profile, a trainer, a model, a dataset, a suite, or a map mix.
**Built-in** ones ship with the app in `<kind>/` (committed; they change
only in code). **Yours** are in `user/<kind>/` (out of git): the ones you
make in the app. One name per kind: a name is looked up in the built-ins
first, and a new file can't take a built-in's name, so a name always
means one file.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
KINDS = (
    "stages", "rules", "rewards", "trainers", "models", "datasets", "suites",
    "mixes",  # 7d5a
)
USER = "user"  # your files: user/<kind>/


def built_in_folder(kind: str, root: Path = REPO) -> Path:
    return root / kind


def user_folder(kind: str, root: Path = REPO) -> Path:
    return root / USER / kind


def find(kind: str, name: str, root: Path = REPO) -> Path:
    """The file named `name`: built-in, else yours. FileNotFoundError if
    neither exists.
    """
    for folder in (built_in_folder(kind, root), user_folder(kind, root)):
        path = folder / f"{name}.json"
        if path.exists():
            return path
    raise FileNotFoundError(
        f"no {kind} file named {name!r} "
        f"(looked in {kind}/ and {USER}/{kind}/)"
    )


def path_of(kind: str, name_or_path: str, root: Path = REPO) -> Path:
    """A name (see `find`), or a path to a .json file as it is. A name
    found nowhere gives the built-in path, so each loader reports the
    missing file its own way.
    """
    path = Path(name_or_path)
    if path.suffix == ".json":
        return path
    try:
        return find(kind, name_or_path, root)
    except FileNotFoundError:
        return built_in_folder(kind, root) / f"{name_or_path}.json"


def names(kind: str, root: Path = REPO) -> list[str]:
    """Every name of the kind, built-in and yours, sorted."""
    found = set()
    for folder in (built_in_folder(kind, root), user_folder(kind, root)):
        found.update(p.stem for p in folder.glob("*.json"))
    return sorted(found)


def ordered(kind: str, root: Path = REPO) -> list[str]:
    """Every name of the kind: the built-ins (sorted), then yours."""
    all_names = names(kind, root)
    built_in = [n for n in all_names if is_built_in(kind, n, root)]
    return built_in + [n for n in all_names if n not in built_in]


def is_built_in(kind: str, name: str, root: Path = REPO) -> bool:
    return (built_in_folder(kind, root) / f"{name}.json").exists()


def new_file(kind: str, name: str, root: Path = REPO) -> Path:
    """Where a new file of yours named `name` goes (its folder made).
    FileExistsError if the name is taken, built-in or yours.
    """
    for folder in (built_in_folder(kind, root), user_folder(kind, root)):
        if (folder / f"{name}.json").exists():
            where = kind if folder.parent == root else f"{USER}/{kind}"
            raise FileExistsError(f"{where}/{name}.json already exists")
    folder = user_folder(kind, root)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{name}.json"
