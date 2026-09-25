import pygame

from src.drivers.actions import Action
from src.drivers.base import Driver
from src.replay.recorder import human_driver


class KeyboardDriver(Driver):
    """You, on the keyboard. Call pygame.event.pump() once per frame
    before acting, so the key state is current.
    """

    name = "keyboard"

    def __init__(self, player: str = "player") -> None:
        self.player = player

    def act(self, observation=None) -> Action:
        keys = pygame.key.get_pressed()
        return (
            bool(keys[pygame.K_a] or keys[pygame.K_LEFT]),
            bool(keys[pygame.K_d] or keys[pygame.K_RIGHT]),
            bool(keys[pygame.K_w] or keys[pygame.K_UP]),
            bool(keys[pygame.K_s] or keys[pygame.K_DOWN]),
            bool(keys[pygame.K_SPACE]),
        )

    def record(self) -> dict:
        return human_driver(self.player, device="keyboard")

    @property
    def label(self) -> str:
        return f"{self.player} (keyboard)"
