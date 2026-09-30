"""Window controls: Esc and the quit prompt, pause, and waiting for your
first key (step 5d).
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402

from src.config import get_maze_car_config  # noqa: E402
from src.envs.maze_car.demo import MazeCarDemo  # noqa: E402
from src.render.renderer import Command, Renderer  # noqa: E402
from src.sim.resources import SimClock  # noqa: E402

GAS = (False, False, True, False, False)
IDLE = (False,) * 5


def _press(renderer, key, game_over=False):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
    return renderer.poll_events(game_over=game_over)


def _renderer():
    return Renderer(get_maze_car_config())


def test_esc_asks_first_and_enter_quits():
    renderer = _renderer()
    assert Command.QUIT not in _press(renderer, pygame.K_ESCAPE)
    assert renderer.confirm_quit and renderer.modal_open
    assert Command.QUIT in _press(renderer, pygame.K_RETURN)


def test_esc_again_goes_back():
    renderer = _renderer()
    _press(renderer, pygame.K_ESCAPE)
    assert Command.QUIT not in _press(renderer, pygame.K_ESCAPE)
    assert not renderer.confirm_quit


def test_enter_reaches_the_mode_without_a_prompt():
    renderer = _renderer()
    assert Command.QUIT not in _press(renderer, pygame.K_RETURN)
    assert renderer.keys_pressed == [pygame.K_RETURN]


def test_the_prompt_takes_only_enter_or_esc():
    renderer = _renderer()
    _press(renderer, pygame.K_ESCAPE)
    assert Command.RESTART not in _press(renderer, pygame.K_r)
    assert renderer.keys_pressed == []  # the mode doesn't see it either
    assert renderer.confirm_quit


def test_esc_closes_the_shortcuts_box_first():
    renderer = _renderer()
    _press(renderer, pygame.K_SLASH)
    assert renderer.show_shortcuts
    assert Command.QUIT not in _press(renderer, pygame.K_ESCAPE)
    assert not renderer.show_shortcuts and not renderer.confirm_quit


def test_esc_quits_at_once_when_the_game_is_over():
    renderer = _renderer()
    assert Command.QUIT in _press(renderer, pygame.K_ESCAPE, game_over=True)


def test_closing_the_window_always_quits():
    renderer = _renderer()
    _press(renderer, pygame.K_ESCAPE)
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    assert Command.QUIT in renderer.poll_events()


# The demo


def _demo(driver="keyboard"):
    config = get_maze_car_config()
    return MazeCarDemo(config, driver=driver, record=False, autorun=False)


def _step(demo):
    return demo.env.world.resource(SimClock).step


def test_your_round_waits_for_your_first_key(monkeypatch):
    demo = _demo()
    monkeypatch.setattr(demo.driver, "act", lambda observation: IDLE)
    for _ in range(10):
        demo.frame(0.1)
    assert _step(demo) == 0  # the timer hasn't started
    assert "driving key" in demo.mode().messages[0][0]
    monkeypatch.setattr(demo.driver, "act", lambda observation: GAS)
    demo.frame(0.1)
    demo.frame(0.1)
    assert _step(demo) > 0 and not demo.waiting


def test_agents_start_at_once():
    demo = _demo("heuristic")
    demo.frame(0.1)
    assert _step(demo) > 0


def test_p_pauses_and_resumes():
    demo = _demo("heuristic")
    demo.frame(0.1)
    demo.env.renderer.keys_pressed = [pygame.K_p]
    demo.frame(0.1)
    step = _step(demo)
    demo.env.renderer.keys_pressed = []
    for _ in range(5):
        demo.frame(0.1)
    assert _step(demo) == step and demo.mode().messages[0][0] == "PAUSED"
    demo.env.renderer.keys_pressed = [pygame.K_p]
    demo.frame(0.1)
    demo.frame(0.1)
    assert _step(demo) > step


def test_an_open_box_freezes_the_game():
    demo = _demo("heuristic")
    demo.frame(0.1)
    demo.env.renderer.confirm_quit = True
    step = _step(demo)
    for _ in range(5):
        demo.frame(0.1)
    assert _step(demo) == step


def test_watching_a_driver_keeps_its_trail():
    demo = _demo("heuristic")
    demo.env.renderer.show_trail = True  # T: drawn under the car
    for _ in range(3):
        demo.frame(0.1)
    mode = demo.mode()
    assert mode.trail is demo.trail
    assert len(demo.trail) == 1 + _step(demo) // 2  # 60 points per second
    assert ("T", "trail: where the car has been") in mode.shortcuts
    assert all(key != "SPACE" for key, _ in mode.shortcuts)  # no driving
    demo.env.reset(seed=1)  # R: a new round, a new trail
    demo.frame(0.1)
    assert len(demo.trail) == 1 + _step(demo) // 2


def test_your_own_driving_has_no_trail():
    demo = _demo()
    assert demo.mode().trail is None and demo.trail == []
