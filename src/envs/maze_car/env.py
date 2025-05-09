from typing import Optional

import pygame
from absl import flags

from src.envs.maze_car.models.action_state import ActionState
from src.envs.maze_car.models.display_state import DisplayState
from src.envs.maze_car.models.field_state import FieldState
from src.envs.maze_car.sprites.car import Car
from src.envs.maze_car.sprites.field import FieldSingleton
from src.envs.maze_car.state import StateSingleton
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
        field: FieldState = self._globals.field
        self.action_state = ActionState()
        self.car = Car(
            x=field.quarter_width - FLAGS.maze_car.car.width // 2,
            y=field.half_height - FLAGS.maze_car.car.height // 2,
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
        self.state.tick()

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

        car = self.car.state.rect
        wh = f"({car.width:3,.0f}, {car.height:3,.0f})"
        cn = f"({car.centerx:3,.0f}, {car.centery:3,.0f})"

        sep = " " * 3
        spd = f"SPD: {s:8,.2f}"
        acc = f"ACC: {a * 100:7,.0f}%"
        agl = f"AGL: {self.car.state.angle:7.0f}°"
        fps = f"FPS: {self.state.clock.get_fps():5.0f}/{mf}"
        dim = f"DIM: {wh:>10s}"
        dim_s = len(dim) * " " + (sep * 2)
        cen = f"CEN: {cn:>10s}"
        cll = f"LSC: {cl:>6.2f}"
        clb = f"BSC: {cb:>6.2f}"
        clf = f"FSC: {cf:>6.2f}"
        clr = f"RSC: {cr:>6.2f}"

        window = get_window_constants(config=FLAGS.maze_car)
        draw_texts(
            surface=self.state.display,
            texts=[
                spd + sep + cen + sep + cll,
                acc + sep + dim + sep + clf,
                agl + dim_s + clr,
                fps + dim_s + clb,
            ],
            size=12,
            x=window.width * 0.025,
            y=window.half_height * 0.075,
        )
