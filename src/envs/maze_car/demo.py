import pygame
from absl import flags

from src.envs.maze_car.env import ActionState, MazeCarEnv
from src.utils.types import Colors

FLAGS = flags.FLAGS


class MazeCarDemo(MazeCarEnv):
    def __init__(self) -> None:
        super().__init__()
        self.run()

    def run(self):
        while self.running:
            self.handle_events()
            self.update()
            self.draw_assets()
            self.update_display()

    def handle_events(self, _=None):
        self.action_state = ActionState()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.mouse_click_events(event)

        self.key_events()

    def mouse_click_events(self, event):
        click_coordinates = event.pos
        if event.button == 1:
            print(f"left click at {click_coordinates}")

    def key_events(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE]:
            self.running = False
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.action_state.turn_left = True
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.action_state.turn_right = True
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.action_state.move_forward = True
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.action_state.move_backward = True

    def draw_assets(self):
        # Background
        self.display.fill(Colors.BLACK)
        self.render_texts()
        self.field.draw(self.display)

        # Static objects

        # Moving objects
        self.car.draw(self.display)
