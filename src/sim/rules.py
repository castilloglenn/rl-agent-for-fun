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
class Collisions:
    """What a wall hit does. The impact speed is the car's speed into the
    wall (px/s), so grazing a wall hurts less than hitting it head-on.
    """

    health: float = 100.0  # a car's full health
    safe_speed: float = 60.0  # hits at or below this do no damage
    lethal_speed: float = 240.0  # hits at or above this wreck the car
    scrape_damage: float = 0.1  # health lost per px slid along a wall

    def damage(self, impact: float) -> float:
        """Health lost by a hit at `impact` px/s: none up to safe_speed,
        rising linearly to all of it at lethal_speed.
        """
        if impact <= self.safe_speed:
            return 0.0
        if impact >= self.lethal_speed:
            return self.health
        share = (impact - self.safe_speed) / (
            self.lethal_speed - self.safe_speed
        )
        return self.health * share


@dataclass(frozen=True)
class Rules:
    name: str
    round_seconds: float
    rounds: int
    scoring: Scoring
    collisions: Collisions
    description: str = ""
    format: int = RULES_FORMAT

    @staticmethod
    def from_dict(data: dict) -> "Rules":
        if data.get("format") != RULES_FORMAT:
            raise RulesError(
                f"unsupported rules format {data.get('format')!r}, "
                f"expected {RULES_FORMAT}"
            )
        if "collisions" not in data:
            raise RulesError("rules need collisions (health and speeds)")
        rules = Rules(
            name=data["name"],
            round_seconds=float(data["round_seconds"]),
            rounds=data["rounds"],
            scoring=Scoring(
                **{k: float(v) for k, v in data.get("scoring", {}).items()}
            ),
            collisions=Collisions(
                **{k: float(v) for k, v in data["collisions"].items()}
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
            "collisions": asdict(self.collisions),
        }

    def validate(self) -> None:
        if self.round_seconds <= 0:
            raise RulesError("round_seconds must be positive")
        if not isinstance(self.rounds, int) or self.rounds < 1:
            raise RulesError("rounds must be a whole number, at least 1")
        if self.scoring.distance_step <= 0:
            raise RulesError("scoring distance_step must be positive")
        collisions = self.collisions
        if collisions.health <= 0:
            raise RulesError("collisions health must be positive")
        if not 0 <= collisions.safe_speed <= collisions.lethal_speed:
            raise RulesError(
                "collisions need 0 <= safe_speed <= lethal_speed"
            )
        if collisions.scrape_damage < 0:
            raise RulesError("collisions scrape_damage can't be negative")

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
