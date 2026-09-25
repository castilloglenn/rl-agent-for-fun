# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A personal reinforcement learning playground. The first environment is **Maze Car**: a top-down pygame car with distance-sensing rays. The goal is for an agent to learn to drive it, and to make that learning visible.

## Commands

Uses Python 3.14 with `venv/`. Use **pygame-ce**, not `pygame`: pygame 2.6.1 has no prebuilt wheel for 3.14 on macOS, and a local build ships without the font module. The two packages can't be installed side by side.

```
source venv/bin/activate
pip install -r requirements.txt
make maze_car      # human-driven demo (python app.py -demo maze_car): WASD/arrows, Esc quits
make run           # python app.py -> src/main.py Main (agent entry point, currently a stub)
make test          # python app.py --tests (currently only prints a TODO)
pytest tests/test_x.py::test_name   # single test (tests/ is currently empty)
```

Config overrides use absl/ml_collections flags, e.g. `python app.py -demo maze_car --maze_car.show_gui=False`.

`.flake8` (max line 80, E501 ignored) and `.pylintrc` exist, but flake8 and pylint are not in `requirements.txt`.

## Architecture

**Config is global via absl flags.** `src/config.py` defines the `tests`/`demo` flags at import time. `app.py` registers the `agent` and `maze_car` `ConfigDict`s under `__main__` before calling `app.run`. Environment code reads `FLAGS.maze_car.*` directly (window size, FPS, car size, acceleration, debug toggles). So env, sprite, and state classes only work once flags are parsed. Tests or scripts that build them outside `app.run` must define and parse these flags first.

**State is split from behavior (MVC-inspired).**
- `src/envs/maze_car/models/*_state.py`: plain dataclasses holding data (car, field, display, action, collision rays).
- `src/envs/maze_car/sprites/*.py`: objects that mutate that state and draw it.
- `src/envs/maze_car/state.py`: `State` is the aggregate. It rejects unknown attributes, and `StateSingleton` holds one global instance. Sprites write their state into it on construction (`self._globals.car = CarState(...)`) and read it back through a `state` property. `FieldSingleton` is a second singleton.

The singletons allow only one car and one environment per process. Planned features (multiple competing cars, parallel environments) need per-car and per-env state, so new code should not add more dependencies on the singletons.

**Environment contract.** `src/envs/base.py` `Environment` defines `reset()`, `get_state()`, `game_step(action) -> (reward, game_over, score)`. An action is a 4-bool tuple mapped by `ActionState` (turn_left, turn_right, move_forward, move_backward). `MazeCarDemo` (`demo.py`) subclasses `MazeCarEnv`: it runs its own loop, builds actions from the keyboard, and is the only class that defines `draw_assets()`. `MazeCarEnv.game_step` calls `draw_assets()` when `show_gui` is on, so the base env doesn't render on its own yet.

**Geometry conventions.** Angles are in degrees: 0 points right, and positive turns counterclockwise on screen (y is inverted in `get_angular_movement_deltas`). The car keeps float remainders in `x_float`/`y_float` for sub-pixel movement over an integer `Rect`. The four collision rays sit at relative angles 0, +30, -30, 180. They currently only clip against the field border rect, since there are no maze walls yet.

**Physics runs on a fixed timestep.** Per-frame speeds are `base_speed / fps` and don't use real elapsed time (`DisplayState.tick_elapsed` is computed but unused). Keep it this way: the planned replay system depends on determinism.

## Current state and direction

The RL side is stubs: `get_state()` returns `None`, the reward is always 0, `game_over` is always `False`, and `Main`/`get_agent_config()` are empty. `torch` is in the requirements but unused.

Planned direction, agreed with the owner:
1. Refine the simulation: maze walls, rays and crashes against walls, real observation and reward.
2. Visualize learning. Train headless at full speed and record episodes (start state, seed, and per-step actions, as JSON Lines). Keep only recordings that beat the best score, and add a replay mode that re-simulates them in the window.
3. Later: multiple competing cars in one window, then parallel environments for faster training.
