import pygame

from src.envs.maze_car import MazeCarEnv


# pylint: disable=E1101
class MazeCarDemo(MazeCarEnv):
    def __init__(self) -> None:
        super().__init__()

        self.run()

    def run(self):
        while self.running:
            self.game_step()

    def handle_events(self):
        self.action_state = ActionState()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.mouse_click_events(event)

        keys = pygame.key.get_pressed()
        self.key_events(keys)

    def mouse_click_events(self, event):
        click_coordinates = event.pos
        if event.button == 1:
            print(f"left click at {click_coordinates}")

    def key_events(self, keys):
        if keys[pygame.K_a]:
            print("a")

        if keys[pygame.K_d]:
            print("d")
