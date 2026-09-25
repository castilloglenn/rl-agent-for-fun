# Architecture (current, pre-refactor)

This describes the code as it is today. It will be rewritten as the refactor lands (see [roadmap](roadmap.md)). The target is an ECS (Entity Component System): see [decision 005](decisions/005-entity-component-system.md).

## Entry point

`app.py` parses flags and chooses a mode: `--tests` (stub), `-demo maze_car` (`MazeCarDemo`), or the default `Main` (stub).

## Config

- `src/config.py` defines the `tests` and `demo` flags when the module is imported.
- `app.py` registers the `agent` and `maze_car` `ConfigDict`s under `__main__`, before `app.run`.
- Env, sprite, and state code read `FLAGS.maze_car.*` directly. That covers window size, FPS, car size, acceleration, and the debug toggles `show_gui`, `show_bounds`, and `show_collision_distance`.

So these classes only work after flags are parsed.

## State vs behavior (MVC-inspired)

| Layer | Location | Role |
|---|---|---|
| Models | `src/envs/maze_car/models/*_state.py` | Dataclasses holding data: car, field, display, action, collision ray |
| Sprites | `src/envs/maze_car/sprites/*.py` | Update that state and draw it with pygame |
| Global state | `src/envs/maze_car/state.py` | `State` aggregate, which rejects unknown attributes. `StateSingleton` holds one instance |

Sprites write their state into the global instance when they're built (`self._globals.car = CarState(...)`), then read it back through a `state` property. `FieldSingleton` is a second singleton, for the field border.

**Limit:** one car and one environment per process.

## Environment contract

`src/envs/base.py` `Environment` defines:

- `reset()`
- `get_state()`, which currently returns `None`
- `game_step(action) -> (reward, game_over, score)`. Currently the reward is always 0 and `game_over` is always `False`.

An action is a 4-bool tuple, mapped by `ActionState` to `(turn_left, turn_right, move_forward, move_backward)`.

## Demo vs env

`MazeCarDemo` (`demo.py`) subclasses `MazeCarEnv`. It runs its own loop, builds actions from the keyboard, and is the only class that defines `draw_assets()`. `MazeCarEnv.game_step` calls `draw_assets()` when `show_gui` is on, so the base env can't render on its own.

## Car

`Car` (`sprites/car.py`) owns four `CollisionDistance` rays (front, left, right, back), and recalculates them after every move or turn. It stops (speed and acceleration drop to 0) when a move would push it outside the field rect.

## Not built yet

Maze walls, crash detection, observation, reward, the agent, training, and replay. `torch` is in the requirements but unused.
