# Config

## Where it's defined

`src/config.py` `get_maze_car_config()` returns a `ConfigDict` with the defaults:

| Key | Default | Used by |
|---|---|---|
| `show_gui` | `True` | `MazeCarEnv`: create a `Renderer` or not. The demo forces it on |
| `show_bounds` | `True` | `Renderer`: draw hitbox rects |
| `show_collision_distance` | `True` | `Renderer`: draw rays |
| `window.title`, `window.width`, `window.height` | `"Maze Car"`, 900, 600 | `Renderer`. `Field` size and `SimConfig.ray_length` are also derived from width and height |
| `display.fps` | 90 | `SimConfig` (per-frame speeds) and `Renderer` (clock tick) |
| `car.width`, `car.height` | 24, 16 | `SimConfig`: start car size |
| `car.acceleration_unit` | 0.25 | `SimConfig`: turn rate floor, and per-frame acceleration |
| `car.acceleration_max` | 2.0 | `SimConfig`: acceleration cap. `Renderer`: HUD percentage |

`get_agent_config()` is empty.

## How it flows

1. `app.py` registers the config dicts as absl flags, so any key can be overridden from the command line (see [setup](setup.md#config-overrides)).
2. `app.py` passes `FLAGS.maze_car` into `MazeCarDemo`. **This is the only place that reads `FLAGS`.**
3. `MazeCarEnv(config)` hands the config to `create_world`, which turns it into the `SimConfig` and `Field` resources, and to `Renderer`.
4. Systems read only resources, never the `ConfigDict` itself.

Tests call `get_maze_car_config()` directly, with no flags.

The behavior fixtures record the physics config, so changing a physics default fails the behavior tests until the fixtures are regenerated.
