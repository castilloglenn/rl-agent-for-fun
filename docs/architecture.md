# Architecture

An ECS (Entity Component System) simulation core, with layers around it. The reasons are in [decision 002](decisions/002-sim-render-split.md) (layers) and [decision 005](decisions/005-entity-component-system.md) (ECS).

```
app.py                 flags -> ConfigDict -> mode (demo / Main stub)
src/ecs/               World: entities, components, resources, systems
src/sim/               Maze Car rules: components, resources, systems, factories
src/envs/maze_car/     MazeCarEnv wraps a World; MazeCarDemo drives it by keyboard
src/render/            Renderer: pygame window, reads the World, never writes it
```

Dependencies point one way: `envs` uses `sim` and `render`, `render` reads `sim` components, and `sim` uses `ecs`. `sim` and `ecs` never import `render` or `envs`.

## ECS core (`src/ecs/world.py`)

- **Entities** are integer IDs, starting at 1 and never reused.
- **Components** are plain dataclasses, stored per type.
- **Resources** are per-world shared objects, one per type.
- **Systems** are functions `system(world)`, run by `world.step()` in the order they were added.
- `world.query(*types, exclude=(...))` returns entities that have all `types` and none of `exclude`, in **ascending ID order**, as a list (safe to delete while looping). Car systems use `exclude=(Eliminated,)`.

Every world is independent. Nothing is global, so several worlds can exist in one process.

## Simulation (`src/sim/`)

| File | Contents |
|---|---|
| `components.py` | Cars: `ActionInput`, `Transform`, `Motion`, `CarSpec`, `Hitbox`, `Ray`/`Sensors`, `PreviousPose`, `Score`, `Eliminated`, `Renderable`. Triggers: `Trigger` (circle), effects `ScoreReward` and `Respawn`, and the `Checkpoint` tag |
| `resources.py` | `SimConfig` (step rate, car size, ray length, driving limits), `GameRules` (scoring), `Rng` (the seed, with one named random stream per use), `Stage`, `Field` (spans the stage from (0, 0)), `SpawnSchedules`, `SimClock`, `RoundState`, and `EventLog` |
| `systems/` | `pose_history_system`, `steering_system`, `movement_system`, `reward_system` (+1 per 10 px forward), `trigger_system` (car touches trigger: apply effects), `sensor_system`, `clock_system`, then `round_system`. The order is fixed by `SIMULATION_SYSTEMS` |
| `elimination.py` | `eliminate(world, car, reason)`: the single way a car leaves a round (walls now, hazards and weapons later). Marks it `Eliminated`, stops it, logs the event |
| `observation.py` | `observe(world, car)`: the agent's 14 normalized inputs, with a versioned layout (`OBSERVATION_NAMES`, `OBSERVATION_VERSION`) |
| `stage.py` | `Stage` (size, walls, spawns, checkpoint rules), `load_stage(name or path)`, validation, and `to_dict()` for embedding in replays |
| `spawning.py` | `SpawnSchedule`: stage + seed decide every spawn. Slot N's candidates depend only on (seed, spawner, N); `random` or `scripted` mode |
| `factories.py` | `create_game(config, label, seed, stage)` (world + car at the stage's spawn + checkpoint: used by the env and tests), `create_world`, `create_car`, `create_start_car`, `create_checkpoint` |
| `geometry.py` | `car_corners` (the 4 real hitbox corners), `inside`, and `max_move_fraction` (how far a move can go before a corner touches the border) |

**The car's position is its float center** (`Transform.x`, `Transform.y`), and `Hitbox` holds its size. The hitbox is the car's 4 real corners. The field border is the only obstacle so far: cars stop exactly on contact (`movement_system`), turns into it are cancelled (`steering_system`), and it stops rays (`sensor_system`).

Geometry and physics rules: [conventions](conventions.md).

## Env (`src/envs/maze_car/env.py`)

`MazeCarEnv` implements `src/envs/base.py` `Environment`, a **Gymnasium-style API** (without the dependency).

**For agents:**
- `reset(seed)` starts a new game (world + car + checkpoint) and returns `(observation, info)`. With `random_seeds=True` (the demo), each reset picks a fresh seed. Otherwise `game.seed` is used.
- `step(action)` returns `(observation, reward, terminated, truncated, info)`:
  - `terminated`: the car is out (a crash).
  - `truncated`: the round ran out of time.
  - `reward`: from the env's **reward profile** (`MazeCarEnv(config, reward="default")`: a name in `rewards/`, a path, or a `RewardProfile`). The profile is a weighted sum of per-step terms (points, checkpoints, crash, time up, per step, distance, speed, steering change, closest wall), and never changes the game score. `rewards/default.json` equals the game points gained. It's 0 once the game is over. See [decision 011](decisions/011-reward-profiles.md).
- `info` has `score`, `points` (game points this step), `checkpoints`, `step`, and `eliminated`.
- `get_state()` returns the observation: 14 float32 values from `observe()` (`src/sim/observation.py`). The names are in `observation_names`, and the version is in `observation_version`. See [game design](game-design.md#observation-what-the-agent-sees).
- An action is 5 bools, in `action_names` order: `(turn_left, turn_right, gas, reverse, brake)`.
- Measured: about 49,000 `step` calls per second on one core, headless (observation and reward included).

**For the real-time demo:**
- `step_world(action)`: one simulation step, no drawing. Does nothing once the game is over.
- `game_step(action)`: `step_world`, plus one drawn frame if `config.show_gui` is on (`step` uses it, so an agent can be watched).
- `render(alpha)`: handles window events (R runs `reset()`) and draws one frame, interpolated by `alpha`. Returns the real seconds since the previous frame.

## Versions

`code_version()` (`src/utils/version.py`) returns the git commit, plus `-dirty` with uncommitted changes (`unknown` without git). Replays and runs record it, so an out-of-date replay shows when the simulation changed.

## Controllers

A controller decides the car's `ActionInput` before each step. The only one today is the keyboard: `read_keyboard()` in `demo.py`. It pumps events, then reads the key state. The agent and the replayer (roadmap steps 4 and 5) will be further controllers.

## Rendering (`src/render/`)

| File | Contents |
|---|---|
| `renderer.py` | `Renderer`: owns the pygame window and clock, draws the field view, and calls the panels |
| `layout.py` | `Layout.for_field`: screen rects for the top bar, field view, side panel, and bottom bar. The window size follows from the field size |
| `panels.py` | Top bar (round, time, score, status; then driver, stage name and size, checkpoint mode, seed), side panel (car, sensor distances, objective, reward, agent view, leaderboard). **Retro style: lines and text only**, with colors and bold for distinction. Graphics belong inside the field, bottom bar (events, step, FPS) |
| `warnings.py` | When HUD values and ray lines turn amber (caution) or red (danger): stopping distance, travel-path rays, speed, time, FPS. Pure functions, shared by the panels and the field |
| `theme.py` | Colors and text sizes |

- `poll_events()`: returns commands: quit (window close or Esc) and restart (R). H toggles the debug lines (rays and hitbox, gated by `show_collision_distance` and `show_bounds`), and a left click prints its **world** coordinates.
- **Round over:** the field shows "ROUND OVER", the reason, the eliminations, and "Press R to restart".
- `draw(world)`: field view (border, cars, optional bounds and rays via `show_bounds` and `show_collision_distance`), then the panels.
- `present()`: display flip (vsync when available), then a clock tick at the frame rate. Returns the real seconds since the last frame.
- **Frame rate:** `display.max_fps` if set, else the detected refresh rate, else 60.
- **Interpolation:** `draw(world, alpha)` draws each car between its `PreviousPose` and current pose. Debug lines move with it.
- **World vs screen coordinates:** the simulation works in world coordinates. The renderer shifts everything by `Renderer.offset` so the field lands in the layout's field view.
- Panel sections for features that don't exist yet show a dash, until their roadmap step fills them in.
- The driver label (for example "You (keyboard)") comes from `Renderable.label`, set through `MazeCarEnv(config, driver=...)`.

It only reads components, so turning it off (`show_gui=False`) never changes the simulation.

## Frame flow (demo)

The simulation runs at a fixed 120 steps/s, and drawing runs at the display's refresh rate ([decision 008](decisions/008-fixed-timestep-clock.md)):

```
every drawn frame:
  read_keyboard()                               -> action
  FixedStepClock.advance(real seconds elapsed)  -> N steps (usually 0 to 2)
  N x env.step_world(action)
        -> world.step(): pose history -> steering -> movement -> sensors -> clock
  env.render(clock.alpha)
        -> poll_events -> draw (cars interpolated) -> present (vsync, tick)
```

`FixedStepClock` (`src/utils/timing.py`) turns real time into a whole number of steps. After a stall it skips the backlog (at most 8 steps per frame).

## Not built yet

Maze walls, crash detection, observation, reward, the agent, training, and replay. `torch` is in the requirements but unused. See [roadmap](roadmap.md).
