# pylint: disable=E1101
from typing import Optional

import pygame
from absl import flags

from src.envs.base import Environment
from src.envs.maze_car.action import ActionState
from src.envs.maze_car.sprite import Car, Field
from src.utils.types import Colors, GameOver, Reward, Score
from src.utils.ui import draw_texts, get_window_constants

FLAGS = flags.FLAGS


class MazeCarEnv(Environment):
    def __init__(self) -> None:
        window = get_window_constants(config=FLAGS.maze_car)

        pygame.init()
        pygame.display.set_caption(window.title)

        self.clock = pygame.time.Clock()
        self.display = pygame.display.set_mode((window.width, window.height))

        self.field = Field()
        self.reset()

    def reset(self) -> None:
        window = get_window_constants(config=FLAGS.maze_car)
        self.action_state = ActionState()
        self.car = Car(
            field=self.field,
            x=window.half_width - FLAGS.maze_car.car.width // 2,
            y=(window.height * 0.58) - FLAGS.maze_car.car.height // 2,
            width=FLAGS.maze_car.car.width,
            height=FLAGS.maze_car.car.height,
            color=Colors.SKY_BLUE,
        )
        self.score: int | float = 0
        self.is_game_over: bool = False
        self.running: bool = True

    def get_state(self) -> tuple:
        pass

    def game_step(
        self, action: Optional[tuple] = None
    ) -> tuple[Reward, GameOver, Score]:
        self.handle_events(action)
        self.update()

        if FLAGS.maze_car.show_gui:
            self.draw_assets()
            self.update_display()

        reward: int | float = self._calculate_reward()
        game_over: bool = False

        return (reward, game_over, self.score)

    def update(self):
        if self.action_state.turn_left:
            if self.action_state.move_backward:
                self.car.turn_right()
            else:
                self.car.turn_left()
        elif self.action_state.turn_right:
            if self.action_state.move_backward:
                self.car.turn_left()
            else:
                self.car.turn_right()

        if self.action_state.move_forward:
            self.car.move_forward()
        elif self.action_state.move_backward:
            self.car.move_backward()

        if not self.action_state.is_moving:
            self.car.set_speed(speed=0, acceleration_rate=0.0)

    def _calculate_reward(self) -> int | float:
        return 0

    def update_display(self):
        pygame.display.update()
        self.clock.tick(FLAGS.maze_car.display.fps)

    def handle_events(self, action):
        self.action_state = ActionState.from_tuple(action)
        if FLAGS.maze_car.show_gui:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False

    def render_texts(self):
        a = self.car.acceleration_rate / FLAGS.maze_car.car.acceleration_max
        s = self.car.base_speed * self.car.speed_multiplier
        cf = self.car.front_collision.distance
        cl = self.car.left_collision.distance
        cr = self.car.right_collision.distance
        cb = self.car.back_collision.distance

        sep = " | "
        fps = f"FPS: {self.clock.get_fps():.0f}"
        spd = f"Speed: {s:,.0f} px/s"
        acc = f"Acceleration: {a*100:,.0f}%"
        agl = f"Angle: {self.car.angle:.0f}°"
        rec = f"{str(self.car.rect)[1:-1].capitalize()}"
        cen = f"Center: {(self.car.rect.center)}"
        fcd = f"Collisions: L:{cl:.0f} | F:{cf:.0f} | R:{cr:.0f} | B:{cb:.0f}"

        window = get_window_constants(config=FLAGS.maze_car)
        draw_texts(
            surface=self.display,
            texts=[
                fps + sep + fcd,
                rec + sep + cen,
                spd + sep + acc + sep + agl,
            ],
            size=20,
            x=window.width * 0.025,
            y=window.half_height * 0.075,
        )
