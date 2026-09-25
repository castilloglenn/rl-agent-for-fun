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
| `resources.py` | `SimConfig` (FPS, acceleration, car size, ray length) and `Field` (drivable area), built from the config |
| `systems/` | `steering_system`, then `movement_system`, then `sensor_system`. The order is fixed by `SIMULATION_SYSTEMS` |
| `factories.py` | `create_world(config)`, `create_car(...)`, `create_start_car(world)` |
| `geometry.py` | `rotated_bounds`: the hitbox size after rotation |

**The car's position is `Hitbox.rect`** (integer pygame `Rect`). `Transform` holds the angle and the sub-pixel carry. The field border is the only obstacle so far: it stops cars (`movement_system`) and rays (`sensor_system`).

Geometry and physics rules: [conventions](conventions.md).

## Env (`src/envs/maze_car/env.py`)

`MazeCarEnv` implements `src/envs/base.py` `Environment`:

- `reset()` builds a new world with one car at the start position.
- `game_step(action)` writes the car's `ActionInput`, calls `world.step()`, and renders if `config.show_gui` is on. It returns `(reward, game_over, score)`.
- `get_state()` returns `None`, the reward is always 0, and `game_over` is always `False` (roadmap step 3).

An action is `(turn_left, turn_right, move_forward, move_backward)`.

## Controllers

A controller decides the car's `ActionInput` before each step. The only one today is the keyboard: `read_keyboard()` in `demo.py`. It pumps events, then reads the key state. The agent and the replayer (roadmap steps 4 and 5) will be further controllers.

## Rendering (`src/render/renderer.py`)

`Renderer` owns the pygame window and clock:

- `poll_events()`: quit on window close or Esc. A left click prints its coordinates.
- `draw(world)`: HUD for the first car, field border, cars, and optionally bounds and rays (`show_bounds`, `show_collision_distance`).
- `present()`: display update, plus a clock tick at the configured FPS.

It only reads components, so turning it off (`show_gui=False`) never changes the simulation.

## Frame flow (demo)

```
read_keyboard() -> env.game_step(action)
                     -> ActionInput on the car
                     -> world.step(): steering -> movement -> sensors
                     -> renderer: poll_events -> draw -> present
```

## Not built yet

Maze walls, crash detection, observation, reward, the agent, training, and replay. `torch` is in the requirements but unused. See [roadmap](roadmap.md).
