from typing import Optional

import pygame
from absl import flags

from envs.maze_car.models.action_state import ActionState
from envs.maze_car.models.display_state import DisplayState
from envs.maze_car.sprites.car import Car
from envs.maze_car.sprites.field import FieldSingleton
from envs.maze_car.state import StateSingleton
from src.envs.base import Environment
from src.utils.types import Colors, GameOver, Reward, Score
from src.utils.ui import draw_texts, get_window_constants

FLAGS = flags.FLAGS


class MazeCarEnv(Environment):
    def __init__(self) -> None:
        window = get_window_constants(config=FLAGS.maze_car)

        pygame.init()
        pygame.display.set_caption(window.title)

        self._globals = StateSingleton.get_instance()
        self._globals.display = DisplayState(
            clock=pygame.time.Clock(),
            display=pygame.display.set_mode((window.width, window.height)),
        )
        self.field = FieldSingleton.get_instance()
        self.reset()

    @property
    def state(self) -> DisplayState:
        return self._globals.display

    def reset(self) -> None:
        window = get_window_constants(config=FLAGS.maze_car)
        self.action_state = ActionState()
        self.car = Car(
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
        self.state.clock.tick(FLAGS.maze_car.display.fps)

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
        mf = FLAGS.maze_car.display.fps
        a = self.car.state.acceleration_rate / FLAGS.maze_car.car.acceleration_max
        s = self.car.state.base_speed * self.car.state.speed_multiplier
        cf = self.car.front_collision.state.distance
        cl = self.car.left_collision.state.distance
        cr = self.car.right_collision.state.distance
        cb = self.car.back_collision.state.distance

        sep = " " * 3
        spd = f"SPD: {s:8,.2f}"
        acc = f"ACC: {a*100:7,.0f}%"
        fps = f"FPS: {self.state.clock.get_fps():5.0f}/{mf}"
        rec = f"REC: {str(self.car.state.rect)[5:-1]:>18s}"
        rec_s = len(rec) * " " + (sep * 2)
        agl = f"AGL: {self.car.state.angle:7.0f}°"
        cen = f"CEN: {str(self.car.state.rect.center):>18s}"
        cll = f"LSC: {cl:5,.0f}"
        clf = f"FSC: {cf:5,.0f}"
        clr = f"RSC: {cr:5,.0f}"
        clb = f"BSC: {cb:5,.0f}"

        window = get_window_constants(config=FLAGS.maze_car)
        draw_texts(
            surface=self.state.display,
            texts=[
                spd + sep + rec + sep + cll,
                acc + sep + cen + sep + clf,
                agl + rec_s + clr,
                fps + rec_s + clb,
            ],
            size=12,
            x=window.width * 0.025,
            y=window.half_height * 0.075,
        )
