"""Game rules files: how a game is played and scored.

A game is stage (where) + rules (how) + seed. The agent's reward profile
is separate and never changes the game. See
docs/decisions/013-game-rules-files.md.
"""

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from src.utils import named_files

RULES_FORMAT = 1
RULES_DIR = Path(__file__).resolve().parents[2] / "rules"


class RulesError(ValueError):
    pass


@dataclass(frozen=True)
class Scoring:
    distance_step: float = 10.0  # px driven forward per +1 point; 0: none
    fuel: float = 100.0  # points per fuel


@dataclass(frozen=True)
class Tank:
    """A car's fuel tank (step 9a2): every throttle and turn burns it, a
    fuel refills it, and an empty one ends the car's round. Rates are per
    second. The same for every car, so a game stays fair.
    """

    capacity: float = 100.0  # full, at the start
    idle: float = 1.0  # always, while the engine runs
    throttle: float = 4.0  # more, with gas or reverse held
    steering: float = 1.5  # more, while turning (9a3)
    refill: float = 25.0  # a fuel's, up to the full tank (9a3)

    def burn(self, throttle: bool, steering: bool) -> float:
        """Fuel a second with these controls (braking burns nothing)."""
        return (
            self.idle
            + (self.throttle if throttle else 0.0)
            + (self.steering if steering else 0.0)
        )


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
    tank: Tank | None = None  # None: no fuel to burn (fuel only scores)

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
            tank=(
                Tank(**{k: float(v) for k, v in data["tank"].items()})
                if data.get("tank")
                else None
            ),
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
            **({"tank": asdict(self.tank)} if self.tank else {}),
        }

    def validate(self) -> None:
        if self.round_seconds <= 0:
            raise RulesError("round_seconds must be positive")
        if not isinstance(self.rounds, int) or self.rounds < 1:
            raise RulesError("rounds must be a whole number, at least 1")
        if self.scoring.distance_step < 0:
            raise RulesError("scoring distance_step can't be negative")
        tank = self.tank
        if tank and tank.capacity <= 0:
            raise RulesError("tank capacity must be positive")
        if tank and min(tank.idle, tank.throttle, tank.steering, tank.refill) < 0:
            raise RulesError("tank burn and refill can't be negative")
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
    path = named_files.path_of("rules", name_or_path)
    return Rules.from_dict(json.loads(path.read_text()))
