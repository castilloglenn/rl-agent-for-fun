# Config

## Where it's defined

`src/config.py` `get_maze_car_config()` returns a `ConfigDict` with the defaults:

| Key | Default | Used by |
|---|---|---|
| `show_gui` | `True` | `MazeCarEnv`: create a `Renderer` or not. The demo forces it on |
| `show_bounds` | `True` | `Renderer`: hitbox lines exist (H toggles all debug lines at runtime) |
| `show_collision_distance` | `True` | `Renderer`: ray lines exist (H toggles all debug lines at runtime) |
| `window.title` | `"Maze Car"` | `Renderer`. The window size is derived from the field size plus the panel layout (`src/render/layout.py`), currently 1203×640 |
| `field.x`, `field.y`, `field.width`, `field.height` | 22.5, 97.5, 855.0, 480.0 | `Field` resource, in world coordinates. The odd origin is a leftover from when the field sat inside a 900×600 window, kept so the physics fixtures stay unchanged |
| `sensors.ray_length` | 1800 | `SimConfig`: maximum ray distance. Longer than the field's diagonal, so today every ray reaches the border |
| `sim.steps_per_second` | 120 | `SimConfig`: the fixed simulation rate. Per-step physics values and step-based durations come from it ([decision 008](decisions/008-fixed-timestep-clock.md)) |
| `hud.reaction_time` | 0.25 s | HUD stopping distance: reaction part (speed × time), plus braking (speed² / 2 × brake) |
| `hud.caution_factor` | 2.0 | Rays on the travel path turn amber below this × stopping distance (red below 1×) |
| `hud.near_caution` | 40.0 px | Proximity: any ray this close turns amber (about 1.7 car lengths) |
| `hud.near_danger` | 15.0 px | Proximity: any ray this close turns red |
| `hud.time_caution`, `hud.time_danger` | 10.0, 5.0 s | TIME turns amber / red below these seconds left |
| `game.seed` | 0 | Seed for checkpoint spawns (agents and tests). The demo picks a fresh one per round |
| `rewards.distance_step` | 10.0 px | Driven forward per +1 point |
| `rewards.checkpoint` | 100 | Points per checkpoint |
| `checkpoint.radius` | 15.0 px | Trigger circle |
| `checkpoint.min_car_distance` | 100.0 px | Spawns at least this far from the car's center |
| `checkpoint.border_margin` | 40.0 px | Spawns at least this far inside the field border |
| `hud.checkpoint_near` | 80.0 px | Checkpoint distance turns green below this |
| `round.seconds` | 60 | Round length. In steps: seconds × `sim.steps_per_second` (7,200) |
| `game.rounds` | 1 | Rounds per game. The game is over when the last round ends |
| `hud.fps_caution`, `hud.fps_danger` | 0.9, 0.5 | FPS turns amber / red below this share of the target frame rate |
| `display.max_fps` | 0 | `Renderer`: frame rate cap. 0 = match the display's refresh rate (auto-detected) |
| `car.width`, `car.height` | 24, 16 | `SimConfig`: start car size |
| `car.max_speed` | 300.0 px/s | Forward speed cap |
| `car.max_reverse_speed` | 100.0 px/s | Reverse speed cap |
| `car.acceleration` | 200.0 px/s² | Gas: 0 to max speed in 1.5 s |
| `car.reverse_acceleration` | 100.0 px/s² | Reverse: 0 to max reverse in 1 s |
| `car.brake_deceleration` | 600.0 px/s² | Brake (and gas/reverse against the direction of motion): max speed to a stop in 0.5 s |
| `car.drag` | 100.0 px/s² | Coasting: max speed to a stop in 3 s |
| `car.max_turn_rate` | 240.0 °/s | Turn rate cap |
| `car.steer_in_time` | 0.25 s | Steering wheel: center to full lock |
| `car.steer_return_time` | 0.15 s | Steering wheel: full lock back to center (self-centering, also used when switching sides) |
| `car.full_turn_speed` | 120.0 px/s | Speed where the max turn rate is reached. Below it, the turn rate scales down to 0 at a stop |

All `car.*` driving values go into `SimConfig`, and `create_car` converts them to per-step units (`CarSpec`).

**Tuning by feel** without editing code: `python app.py -demo maze_car --maze_car.car.max_speed=250 --maze_car.car.max_turn_rate=270`

`get_agent_config()` is empty.

## How it flows

1. `app.py` registers the config dicts as absl flags, so any key can be overridden from the command line (see [setup](setup.md#config-overrides)).
2. `app.py` passes `FLAGS.maze_car` into `MazeCarDemo`. **This is the only place that reads `FLAGS`.**
3. `MazeCarEnv(config)` hands the config to `create_world`, which turns it into the `SimConfig` and `Field` resources, and to `Renderer`.
4. Systems read only resources, never the `ConfigDict` itself.

Tests call `get_maze_car_config()` directly, with no flags.

The behavior fixtures record the physics config, so changing a physics default fails the behavior tests until the fixtures are regenerated.
