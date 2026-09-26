"""Drivers by name, for the command line and the runner."""

from src.drivers.base import Driver
from src.drivers.heuristic import CompassDriver
from src.drivers.random_driver import RandomDriver

BASELINES = {
    "random": RandomDriver,
    "heuristic": CompassDriver,
}


class DriverError(ValueError):
    """A driver name that can't be made: unknown, or a missing or
    incompatible agent.
    """


def make_driver(name: str, player: str = "player") -> Driver:
    """A driver by name: "keyboard", a baseline, or "agent:<id>" (an agent
    in agents/, at its best scored checkpoint, else its newest;
    "agent:<id>@<checkpoint>" or "@best" for a specific one).
    """
    if name.startswith("agent:"):
        from src.agents.driver import AgentDriver
        from src.agents.store import AgentError

        agent, _, checkpoint = name.removeprefix("agent:").partition("@")
        try:
            return AgentDriver.load(agent, checkpoint or None)
        except AgentError as error:
            raise DriverError(str(error)) from error
    if name == "keyboard":
        from src.drivers.keyboard import KeyboardDriver

        return KeyboardDriver(player)
    if name not in BASELINES:
        known = ", ".join(["keyboard", *BASELINES, "agent:<id>"])
        raise DriverError(f"unknown driver {name!r} (known: {known})")
    return BASELINES[name]()
