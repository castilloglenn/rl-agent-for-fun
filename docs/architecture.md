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
- `world.query(*types)` returns matching entities in **ascending ID order**, as a list (safe to delete while looping).

Every world is independent. Nothing is global, so several worlds can exist in one process.

## Simulation (`src/sim/`)

| File | Contents |
|---|---|
| `components.py` | `ActionInput`, `Transform`, `Motion`, `CarSpec`, `Hitbox`, `Ray`/`Sensors`, `Renderable` |
| `resources.py` | `SimConfig` (FPS, car size, ray length, driving limits), `Field` (drivable area), and `SimClock` (steps simulated so far), built from the config |
| `systems/` | `pose_history_system` (remembers each car's pose for interpolated drawing), `steering_system`, `movement_system`, `sensor_system`, then `clock_system`. The order is fixed by `SIMULATION_SYSTEMS` |
| `factories.py` | `create_world(config)`, `create_car(...)`, `create_start_car(world)` |
| `geometry.py` | `rotated_bounds`: the hitbox size after rotation |

**The car's position is `Hitbox.rect`** (integer pygame `Rect`). `Transform` holds the angle and the sub-pixel carry. The field border is the only obstacle so far: it stops cars (`movement_system`) and rays (`sensor_system`).

Geometry and physics rules: [conventions](conventions.md).

## Env (`src/envs/maze_car/env.py`)

`MazeCarEnv` implements `src/envs/base.py` `Environment`:

- `reset()` builds a new world with one car at the start position.
- `step_world(action)` writes the car's `ActionInput` and calls `world.step()` (one simulation step, no drawing). It returns `(reward, game_over, score)`.
- `game_step(action)` is `step_world` plus one drawn frame if `config.show_gui` is on. That's the agent-facing API.
- `render(alpha)` handles window events and draws one frame, interpolated by `alpha`. It returns the real seconds since the previous frame.
- `get_state()` returns `None`, the reward is always 0, and `game_over` is always `False` (roadmap step 3).

An action is `(turn_left, turn_right, gas, reverse, brake)`.

## Controllers

A controller decides the car's `ActionInput` before each step. The only one today is the keyboard: `read_keyboard()` in `demo.py`. It pumps events, then reads the key state. The agent and the replayer (roadmap steps 4 and 5) will be further controllers.

## Rendering (`src/render/`)

| File | Contents |
|---|---|
| `renderer.py` | `Renderer`: owns the pygame window and clock, draws the field view, and calls the panels |
| `layout.py` | `Layout.for_field`: screen rects for the top bar, field view, side panel, and bottom bar. The window size follows from the field size |
| `panels.py` | Top bar (round, time, score, status, driver), side panel (car, sensor distances, objective, reward, agent view, leaderboard). **Retro style: lines and text only**, with colors and bold for distinction. Graphics belong inside the field, bottom bar (events, step, FPS) |
| `theme.py` | Colors and text sizes |

- `poll_events()`: quit on window close or Esc, H toggles the debug lines (rays and hitbox, gated by `show_collision_distance` and `show_bounds`), and a left click prints its **world** coordinates.
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
