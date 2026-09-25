# Roadmap

Goal: see how an RL agent learns to drive Maze Car.

## Step order

| # | Step | Status |
|---|---|---|
| 1 | Behavior tests that pin down current car physics (the refactor safety net, later the determinism test) | Next |
| 2 | Refactor: sim/render split, remove singletons and global `FLAGS` reads. **Structure only** | Planned |
| 3 | Simulation: maze walls, rays and crashes against walls, observation, reward | Planned |
| 4 | Replay: headless training, recording episodes that improve on the best, replay mode | Planned |
| 5 | Agent: torch model and training loop | Planned |
| 6 | Polygon hitbox, then multiple competing cars with car-vs-car collision | Planned |
| 7 | Parallel environments for faster training | Planned |

## Refactor scope (step 2)

In scope:
- Removing `StateSingleton`/`FieldSingleton`, and passing config in explicitly
- Splitting simulation (`sim/`) from drawing (`render/`)
- Moving the existing logic into `Car` and `World` objects

Out of scope: any behavior change. The demo must look and drive the same, as the step 1 tests check. That includes keeping the current `Rect` hitbox.

## Target layout

Described in [decision 002](decisions/002-sim-render-split.md).
