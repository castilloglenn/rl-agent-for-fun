# Roadmap

Goal: see how an RL agent learns to drive Maze Car.

## Step order

| # | Step | Status |
|---|---|---|
| 1 | Behavior tests that pin down current car physics (the refactor safety net, later the determinism test) | Next |
| 2 | Refactor into ECS: sim/render split, remove singletons and global `FLAGS` reads. **Structure only** | Planned |
| 3 | Simulation: maze walls, rays and crashes against walls, observation, reward | Planned |
| 4 | Replay: headless training, recording episodes that improve on the best, replay mode | Planned |
| 5 | Agent: torch model and training loop | Planned |
| 6 | Polygon hitbox, then multiple competing cars with car-vs-car collision | Planned |
| 7 | Parallel environments for faster training | Planned |

## Refactor scope (step 2)

In scope:
- A small in-house ECS core (entities, components, systems, resources)
- Replacing `StateSingleton`/`FieldSingleton` and global `FLAGS` reads with per-world resources
- Moving the car state into components, and the car logic into steering, movement, and sensor systems
- Moving drawing into a render system, separate from the simulation step

Out of scope: any behavior change. The demo must look and drive the same, as the step 1 tests check. That includes keeping the current `Rect` hitbox.

## Target layout

Layers: [decision 002](decisions/002-sim-render-split.md). ECS structure and component and system mapping: [decision 005](decisions/005-entity-component-system.md).
