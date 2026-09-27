"""The make commands, read from the Makefile itself (roadmap step 6a).

The Makefile stays the one list of commands: the control center reads
each target's group and description (from `make help`), its parameters
and their examples (the `require` lines), and the command it runs. So the
two never drift apart.
"""

import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path

MAKEFILE = Path(__file__).resolve().parents[2] / "Makefile"
HIDDEN = ("help", "control")  # not runnable from the control center
# Commands that open a game window (the rest run headless).
WINDOW_FLAGS = (
    "-demo",
    "-replay",
    "-replay_last",
    "-best_replay",
    "-showcase",
)

_TARGET = re.compile(r"^([a-z_]+):\s*$")
_REQUIRE = re.compile(r"\$\(call require,([A-Z_]+),([^)]*)\)")
_GROUP = re.compile(r'^\t@echo "([A-Z][^"]*)"$')
_USAGE = re.compile(
    r'^\t@echo "  make ([a-z_]+)((?: [A-Z_]+=\S+)*)\s{2,}(.+)"$'
)


@dataclass(frozen=True)
class Param:
    name: str  # for example "AGENT"
    example: str  # the Makefile's example value


@dataclass(frozen=True)
class MakeCommand:
    name: str  # the make target, for example "train"
    group: str  # its heading in make help, for example "Agents"
    description: str
    params: tuple[Param, ...]
    command: str  # the recipe line, with $(PARAM) placeholders

    @property
    def opens_window(self) -> bool:
        return any(flag in self.command.split() for flag in WINDOW_FLAGS)

    def make_line(self, values: dict[str, str]) -> str:
        """How you'd type it: make train AGENT=rookie."""
        params = " ".join(
            f"{p.name}={values.get(p.name, '')}" for p in self.params
        )
        return f"make {self.name}" + (f" {params}" if params else "")

    def argv(self, values: dict[str, str]) -> list[str]:
        """The command to run, with the parameters filled in."""
        missing = [p.name for p in self.params if not values.get(p.name)]
        if missing:
            example = self.make_line({p.name: p.example for p in self.params})
            raise ValueError(
                f"{self.name} needs {', '.join(missing)} (e.g. {example})"
            )
        line = self.command
        for param in self.params:
            line = line.replace(f"$({param.name})", values[param.name])
        argv = shlex.split(line)
        if argv[0] == "python":
            argv[0] = sys.executable  # the project's own Python
        return argv


def read_commands(path: Path = MAKEFILE) -> list[MakeCommand]:
    """Every documented make target, in make help order."""
    lines = path.read_text().splitlines()
    groups, descriptions, order = {}, {}, []
    group = ""
    for line in lines:
        if match := _GROUP.match(line):
            group = match.group(1).split(" (")[0]
        elif match := _USAGE.match(line):
            name = match.group(1)
            groups[name], descriptions[name] = group, match.group(3).strip()
            order.append(name)

    recipes: dict[str, list[str]] = {}
    current = None
    for line in lines:
        if match := _TARGET.match(line):
            current = match.group(1)
            recipes[current] = []
        elif current and line.startswith("\t"):
            recipes[current].append(line.strip())
        elif not line.strip():
            current = None

    commands = []
    for name in order:
        if name in HIDDEN or name not in recipes:
            continue
        recipe = recipes[name]
        params = tuple(
            Param(m.group(1), m.group(2))
            for line in recipe
            for m in _REQUIRE.finditer(line)
        )
        command = next(
            line for line in recipe if line.startswith("python ")
        )
        commands.append(
            MakeCommand(
                name, groups[name], descriptions[name], params, command
            )
        )
    return commands
