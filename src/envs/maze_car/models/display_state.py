from dataclasses import dataclass
from pygame import Surface

from pygame.time import Clock


@dataclass
class DisplayState:
    clock: Clock = Clock()
    display: Surface = Surface((0, 0))
