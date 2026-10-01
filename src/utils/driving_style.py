"""Driving style (roadmap 7c9, decision 046): how an agent spends its steps,
counted while its checkpoints are scored (no extra games). Found needed on
2026-09-30: agent-1 drove backward 91 to 100 % of the time, and its scores
alone didn't say so.

No torch here: the control center reads it too.
"""

PEDALS = ("forward", "brake", "coast", "reverse")  # they add up to 1
TURNS = ("left", "right")  # the rest of the steps go straight
COLUMNS = (
    *(f"style_{p}" for p in PEDALS),
    *(f"style_{t}" for t in TURNS),
    "style_backward",  # the car actually moving backward
)
# (column, above this share, what it says)
WARNINGS = (
    ("style_backward", 0.40, "drives backward most of the time"),
    ("style_brake", 0.50, "brakes most of the time"),
    ("style_coast", 0.70, "coasts most of the time"),
    ("style_left", 0.80, "circles left"),
    ("style_right", 0.80, "circles right"),
)


def pedal(action) -> str:
    """An action's pedal, in the game's order: brake beats gas, and gas
    beats reverse. `action`: (turn_left, turn_right, gas, reverse, brake).
    """
    _, _, gas, reverse, brake = action
    if brake:
        return "brake"
    if gas:
        return "forward"
    return "reverse" if reverse else "coast"


def turn(action) -> str | None:
    """Left, right, or None (straight; both at once re-center)."""
    left, right = action[0], action[1]
    if left and not right:
        return "left"
    if right and not left:
        return "right"
    return None


class Counter:
    """Counts one game's steps (or many games')."""

    def __init__(self) -> None:
        self.steps = 0
        self.counts = {column: 0 for column in COLUMNS}

    def add(self, action, speed: float) -> None:
        self.steps += 1
        self.counts[f"style_{pedal(action)}"] += 1
        direction = turn(action)
        if direction:
            self.counts[f"style_{direction}"] += 1
        if speed < 0:
            self.counts["style_backward"] += 1

    def merge(self, other: "Counter") -> None:
        self.steps += other.steps
        for column, count in other.counts.items():
            self.counts[column] += count

    def shares(self) -> dict[str, float]:
        steps = self.steps or 1
        return {c: n / steps for c, n in self.counts.items()}


def warnings(scores: dict) -> list[str]:
    """What a style says that the scores don't (empty: a good mix)."""
    return [
        text
        for column, above, text in WARNINGS
        if scores.get(column) is not None and scores[column] > above
    ]


def summary(scores: dict) -> str:
    """forward 62% · brake 8% · coast 20% · reverse 10% · left 30% ·
    right 28% · backward 12% ("" if it wasn't measured).
    """
    if scores.get("style_forward") is None:
        return ""
    parts = [f"{p} {scores[f'style_{p}']:.0%}" for p in PEDALS]
    parts += [f"{t} {scores[f'style_{t}']:.0%}" for t in TURNS]
    parts.append(f"backward {scores['style_backward']:.0%}")
    return " · ".join(parts)
