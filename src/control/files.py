"""Editing the named files (roadmap step 6d1): reward profiles, rules,
trainers, models, datasets, and suites.

A file becomes a list of fields, one per value, by its path in the file
(`scoring.checkpoint`, `scenarios.1.episodes`), and the edited fields
become the file again. Every edit is checked with the same `from_dict`
the commands use, and saving writes the file laid out the way the files
in the repo are: small flat objects inline near the top, the rest one
value per line. Stages aren't here: the map editor (step 7) edits them.
"""

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.utils import named_files

REPO = Path(__file__).resolve().parents[2]
NAME = re.compile(r"^[A-Za-z0-9_-]+$")
WIDTH = 100  # an inline object's line stays within this
INLINE_DEPTH = 2  # objects deeper than this are never inline


class FileError(ValueError):
    pass


@dataclass(frozen=True)
class Kind:
    label: str
    folder: str
    defaults: tuple[str, ...]  # the code relies on these: never deleted

    def validate(self, data: dict) -> None:
        VALIDATORS[self.folder](data)


def _rewards(data: dict) -> None:
    from src.envs.maze_car.rewards import RewardProfile

    RewardProfile.from_dict(data)


def _rules(data: dict) -> None:
    from src.sim.rules import Rules

    Rules.from_dict(data)


def _trainers(data: dict) -> None:
    from src.agents.trainer import ImitationSpec, TrainerSpec

    if data.get("algorithm") == "imitation":
        ImitationSpec.from_dict(data)
    else:
        TrainerSpec.from_dict(data)


def _models(data: dict) -> None:
    from src.agents.model import ModelSpec

    ModelSpec.from_dict(data)


def _datasets(data: dict) -> None:
    from src.experiments.datasets import DatasetSpec

    DatasetSpec.from_dict(data)


def _suites(data: dict) -> None:
    # The suite module loads torch (about 1 s, the first time only).
    from src.experiments.evaluation import Suite

    Suite.from_dict(data)


VALIDATORS: dict[str, Callable[[dict], None]] = {
    "rewards": _rewards,
    "rules": _rules,
    "trainers": _trainers,
    "models": _models,
    "datasets": _datasets,
    "suites": _suites,
}
KINDS = (
    Kind("Reward profiles", "rewards", ("default",)),
    Kind("Rules", "rules", ("standard",)),
    Kind("Trainers", "trainers", ("default", "imitate")),
    Kind("Models", "models", ("small",)),
    Kind("Datasets", "datasets", ("mine",)),
    Kind("Suites", "suites", ("box",)),
)
# Values tied to code or to the file's shape: shown, not edited.
READONLY = {
    "name",
    "algorithm",
    "observation_version",
    "actions",
    "scenarios.*.kind",
}
HIDDEN = {"format"}


def check(kind: Kind, data: dict) -> str | None:
    """The first problem with `data`, in plain words, or None."""
    try:
        kind.validate(data)
    except (ValueError, TypeError, KeyError) as error:
        text = str(error)
        if isinstance(error, KeyError):
            text = f"missing {text}"
        return text.strip("'\"") or type(error).__name__
    return None


# Fields


@dataclass(frozen=True)
class Item:
    path: str  # "scoring.checkpoint", "terms.points", "scenarios.1.name"
    text: str  # the value as typed
    type: str  # "number", "text", "list", "bool", "choice", "readonly"
    options: tuple[str, ...] = ()  # for "bool" and "choice"
    hint: str = ""  # what a blank typed field means


def _choices(folder: str, path: str, repo: Path) -> tuple[str, ...] | None:
    generic = re.sub(r"\.\d+\.", ".*.", path)
    if folder == "datasets" and path == "include":
        return ("all", "kept")
    if folder == "models" and path == "activation":
        from src.agents.model import ACTIVATIONS

        return tuple(ACTIVATIONS)
    if folder == "suites" and generic in ("scenarios.*.stage",):
        return tuple(named_files.names("stages", repo))
    if folder == "suites" and generic in ("scenarios.*.rules",):
        return tuple(named_files.names("rules", repo))
    return None


def items(folder: str, data: dict, repo: Path = REPO) -> list[Item]:
    """The file as fields, in the file's order."""
    if folder == "rewards":
        return _reward_items(data)
    found: list[Item] = []
    _walk(folder, data, "", found, repo)
    return found


def _walk(folder, value, path, found, repo) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            full = f"{path}.{key}" if path else key
            if full not in HIDDEN:
                _walk(folder, child, full, found, repo)
        return
    if isinstance(value, list) and any(isinstance(v, dict) for v in value):
        for i, child in enumerate(value):
            _walk(folder, child, f"{path}.{i}", found, repo)
        return
    generic = re.sub(r"\.\d+\.", ".*.", path)
    if path in READONLY or generic in READONLY:
        found.append(Item(path, _text(value), "readonly"))
    elif isinstance(value, bool):
        found.append(Item(path, _text(value), "bool", ("true", "false")))
    elif isinstance(value, (int, float)):
        found.append(Item(path, _text(value), "number"))
    elif isinstance(value, list):
        found.append(Item(path, _text(value), "list"))
    else:
        options = _choices(folder, path, repo)
        if options:
            found.append(Item(path, _text(value), "choice", options))
        else:
            found.append(Item(path, _text(value), "text"))


def _text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(_text(v) for v in value)
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _reward_items(data: dict) -> list[Item]:
    """Every known term, so one can be added or dropped: a blank weight
    leaves it out. Parameters show under their term.
    """
    from src.envs.maze_car.rewards import TERMS

    found = [
        Item("name", data.get("name", ""), "readonly"),
        Item("description", data.get("description", ""), "text"),
    ]
    terms = data.get("terms") or {}
    order = list(terms) + [t for t in TERMS if t not in terms]
    for term in order:
        spec = terms.get(term)
        weight = spec.get("weight") if isinstance(spec, dict) else spec
        found.append(
            Item(
                f"terms.{term}",
                "" if weight is None else _text(weight),
                "number",
                hint="blank: not used",
            )
        )
        params = TERMS[term].params if term in TERMS else {}
        for param, default in params.items():
            given = spec.get(param) if isinstance(spec, dict) else None
            found.append(
                Item(
                    f"terms.{term}.{param}",
                    "" if given is None else _text(given),
                    "number",
                    hint=f"blank: {default:g}",
                )
            )
    return found


def rebuild(folder: str, original: dict, values: dict[str, str]) -> dict:
    """The edited file. Raises FileError for a value that isn't what its
    field holds (for example text in a number).
    """
    data = deepcopy(original)
    if folder == "rewards":
        return _rebuild_rewards(data, values)
    for path, text in values.items():
        old = _get(data, path)
        _set(data, path, _parse(path, text, old))
    return data


def _parse(path: str, text: str, old):
    text = text.strip()
    if isinstance(old, bool):
        return text == "true"
    if isinstance(old, (int, float)):
        return _number(path, text)
    if isinstance(old, list):
        parts = [p.strip() for p in text.split(",") if p.strip()]
        sample = old[0] if old else ""
        if isinstance(sample, (int, float)) and not isinstance(sample, bool):
            return [_number(path, p) for p in parts]
        return parts
    return text


def _number(path: str, text: str):
    if not text:
        raise FileError(f"{path}: needs a number")
    try:
        return int(text) if re.fullmatch(r"-?\d+", text) else float(text)
    except ValueError:
        raise FileError(f"{path}: {text!r} isn't a number") from None


def _rebuild_rewards(data: dict, values: dict[str, str]) -> dict:
    from src.envs.maze_car.rewards import TERMS

    data["description"] = values.get("description", "").strip()
    old = data.get("terms") or {}
    order = list(old) + [t for t in TERMS if t not in old]
    terms = {}
    for term in order:
        weight = values.get(f"terms.{term}", "").strip()
        params = {}
        for param in TERMS[term].params if term in TERMS else {}:
            given = values.get(f"terms.{term}.{param}", "").strip()
            if given:
                params[param] = _number(f"terms.{term}.{param}", given)
        if not weight:
            if params:
                raise FileError(f"terms.{term}: a parameter needs a weight")
            continue
        weight = _number(f"terms.{term}", weight)
        terms[term] = {"weight": weight, **params} if params else weight
    data["terms"] = terms
    return data


def _keys(path: str) -> list:
    return [int(p) if p.isdigit() else p for p in path.split(".")]


def _get(data, path: str):
    for key in _keys(path):
        data = data[key]
    return data


def _set(data, path: str, value) -> None:
    keys = _keys(path)
    for key in keys[:-1]:
        data = data[key]
    data[keys[-1]] = value


# Reading and writing


def names(repo: Path, kind: "Kind") -> tuple[str, ...]:
    """The kind's files, built-in and yours."""
    return tuple(named_files.names(kind.folder, repo))


def dump(data: dict) -> str:
    """The file's text, laid out like the repo's files (so saving an
    unchanged file changes nothing).
    """
    return _dump(data, 0, 0) + "\n"


def _flat(value) -> bool:
    inner = value.values() if isinstance(value, dict) else value
    return not any(isinstance(v, (dict, list)) for v in inner)


def _dump(value, indent: int, prefix: int) -> str:
    inline = json.dumps(value, ensure_ascii=False)
    if not isinstance(value, (dict, list)) or not value:
        return inline
    depth = indent // 2
    fits = indent + prefix + len(inline) <= WIDTH
    if 0 < depth <= INLINE_DEPTH and _flat(value) and fits:
        return inline
    pad = " " * (indent + 2)
    if isinstance(value, dict):
        rows = []
        for key, child in value.items():
            name = json.dumps(key, ensure_ascii=False) + ": "
            rows.append(pad + name + _dump(child, indent + 2, len(name)))
        return "{\n" + ",\n".join(rows) + "\n" + " " * indent + "}"
    rows = [pad + _dump(child, indent + 2, 0) for child in value]
    return "[\n" + ",\n".join(rows) + "\n" + " " * indent + "]"


BUILT_IN = (
    "a built-in file ships with the app and changes only in code: "
    "duplicate it to make your own"
)


def load(repo: Path, kind: Kind, name: str) -> dict:
    return json.loads(named_files.find(kind.folder, name, repo).read_text())


def save(repo: Path, kind: Kind, name: str, data: dict) -> dict:
    """Writes the file where it is (a new one: in user/). A suite whose
    content changed gets the next version, so old scores stay apart from
    new ones. Returns what was written.
    """
    if named_files.is_built_in(kind.folder, name, repo):
        raise FileError(BUILT_IN)
    try:
        path = named_files.find(kind.folder, name, repo)
    except FileNotFoundError:
        path = named_files.new_file(kind.folder, name, repo)
    if kind.folder == "suites" and path.exists():
        before = json.loads(path.read_text())
        if _without_version(before) != _without_version(data):
            data = {**data, "version": before.get("version", 0) + 1}
    problem = check(kind, data)
    if problem:
        raise FileError(problem)
    path.write_text(dump(data))
    return data


def _without_version(data: dict) -> dict:
    return {k: v for k, v in data.items() if k != "version"}


def duplicate(repo: Path, kind: Kind, name: str, new: str) -> Path:
    """A copy under a new name (a new suite starts at version 1)."""
    new = new.strip()
    if not NAME.match(new):
        raise FileError("a name uses letters, digits, - and _ only")
    data = {**load(repo, kind, name), "name": new}
    try:
        target = named_files.new_file(kind.folder, new, repo)  # in user/
    except FileExistsError as error:
        raise FileError(str(error))
    if kind.folder == "suites":
        data["version"] = 1
    target.write_text(dump(data))
    return target
