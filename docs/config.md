# Config

## Where it's defined

`src/config.py` `get_maze_car_config()` returns a `ConfigDict` with the defaults:

| Key | Default | Used by |
|---|---|---|
| `show_gui` | `True` | `MazeCarEnv`: create a `Renderer` or not. The demo forces it on |
| `show_bounds` | `True` | `Renderer`: draw hitbox rects |
| `show_collision_distance` | `True` | `Renderer`: draw rays |
| `window.title` | `"Maze Car"` | `Renderer`. The window size is derived from the field size plus the panel layout (`src/render/layout.py`), currently 1203×640 |
| `field.x`, `field.y`, `field.width`, `field.height` | 22.5, 97.5, 855.0, 480.0 | `Field` resource, in world coordinates. The odd origin is a leftover from when the field sat inside a 900×600 window, kept so the physics fixtures stay unchanged |
| `sensors.ray_length` | 1800 | `SimConfig`: how far rays are cast before clipping at the field |
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
