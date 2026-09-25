"""Game rules files: how a game is played and scored.

A game is stage (where) + rules (how) + seed. The agent's reward profile
is separate and never changes the game. See
docs/decisions/013-game-rules-files.md.
"""

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

RULES_FORMAT = 1
RULES_DIR = Path(__file__).resolve().parents[2] / "rules"


class RulesError(ValueError):
    pass


@dataclass(frozen=True)
class Scoring:
    distance_step: float = 10.0  # px driven forward per +1 point
    checkpoint: float = 100.0  # points per checkpoint


@dataclass(frozen=True)
class Rules:
    name: str
    round_seconds: float
    rounds: int
    scoring: Scoring
    description: str = ""
    format: int = RULES_FORMAT

    @staticmethod
    def from_dict(data: dict) -> "Rules":
        if data.get("format") != RULES_FORMAT:
            raise RulesError(
                f"unsupported rules format {data.get('format')!r}, "
                f"expected {RULES_FORMAT}"
            )
        rules = Rules(
            name=data["name"],
            round_seconds=float(data["round_seconds"]),
            rounds=data["rounds"],
            scoring=Scoring(
                **{k: float(v) for k, v in data.get("scoring", {}).items()}
            ),
            description=data.get("description", ""),
        )
        rules.validate()
        return rules

    def to_dict(self) -> dict:
        """Plain data, in the file's layout. Replays and runs record it."""
        return {
            "format": self.format,
            "name": self.name,
            "description": self.description,
            "round_seconds": self.round_seconds,
            "rounds": self.rounds,
            "scoring": asdict(self.scoring),
        }

    def validate(self) -> None:
        if self.round_seconds <= 0:
            raise RulesError("round_seconds must be positive")
        if not isinstance(self.rounds, int) or self.rounds < 1:
            raise RulesError("rounds must be a whole number, at least 1")
        if self.scoring.distance_step <= 0:
            raise RulesError("scoring distance_step must be positive")

    def with_round_seconds(self, seconds: float) -> "Rules":
        """These rules with another round length, under a new name (so
        leaderboards never mix it with the original).
        """
        return replace(
            self,
            name=f"{self.name}-{seconds:g}s",
            round_seconds=float(seconds),
        )


def load_rules(name_or_path: str) -> Rules:
    """Rules by name (rules/<name>.json) or by file path."""
    path = Path(name_or_path)
    if path.suffix != ".json":
        path = RULES_DIR / f"{name_or_path}.json"
    return Rules.from_dict(json.loads(path.read_text()))
