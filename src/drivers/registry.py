"""Drivers by name, for the command line and the runner."""

from src.drivers.base import Driver
from src.drivers.heuristic import CompassDriver
from src.drivers.random_driver import RandomDriver

BASELINES = {
    "random": RandomDriver,
    "heuristic": CompassDriver,
}


def make_driver(name: str, player: str = "player") -> Driver:
    """A driver by name: "keyboard", or a baseline."""
    if name == "keyboard":
        from src.drivers.keyboard import KeyboardDriver

        return KeyboardDriver(player)
    if name not in BASELINES:
        known = ", ".join(["keyboard", *BASELINES])
        raise ValueError(f"unknown driver {name!r} (known: {known})")
    return BASELINES[name]()
