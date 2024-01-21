from dataclasses import dataclass, field

from absl import flags
from pygame import Surface

from pygame.time import Clock

FLAGS = flags.FLAGS


@dataclass
class DisplayState:
    clock: Clock = Clock()
    display: Surface = Surface((0, 0))

    tick_elapsed: float = field(init=False)

    def __post_init__(self):
        self.tick_elapsed = 0.0

    def tick(self):
        self.tick_elapsed = self.clock.tick(FLAGS.maze_car.display.fps) / 1000.0
