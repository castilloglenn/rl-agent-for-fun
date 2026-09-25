# Roadmap

Goal: train real RL agents in Maze Car, watch how they learn, run experiments on them, and play alongside them.

## Step order

| # | Step | Status |
|---|---|---|
| 1 | Behavior tests that pin down current car physics (the refactor safety net, later the determinism test) | Done |
| 2 | Refactor into ECS: sim/render split, remove singletons and global `FLAGS` reads. **Structure only** | Done |
| 2a | ECS core (`src/ecs/`): World, entities, components, resources, systems, with unit tests | Done |
| 2b | Car components, systems (steering, movement, sensors), and factories in `src/sim/`. Behavior tests run against both old and new code | Done |
| 2c | Render system, then switch the demo and env to the ECS. Removed the legacy test runner, since it needed the old env | Done |
| 2d | Delete the old singletons, models, and sprites (dead code since 2c), and rewrite `architecture.md` | Done |
| 3 | Simulation: maze walls, rays and crashes against walls, observation, reward. **Blocked on the game goal** (see open questions) | Next |
| 4 | Replay and experiment runs: headless episodes, recordings of new bests, replay mode, one folder per run | Planned |
| 5 | Agent and training: torch model, training loop, full checkpoints, pause / resume / branch | Planned |
| 6 | Control center GUI: its own window (runs panel, learning curves, terminal-style console), plus separate simulation windows for live play and replays | Planned |
| 7 | Multiple cars: ghost mode first (you join agents, no car-vs-car collision), then polygon hitbox and car-vs-car collision, then competition | Planned |
| 8 | Parallel environments for faster training | Planned |

## Step details

### 4. Replay and experiment runs

Replays: see [decision 003](decisions/003-replay-over-multi-window.md).

Each training run gets its own folder:

```
runs/<date>_<name>_seed<N>/
  config.json     all settings: reward, sensors, network, learning rate, seed
  metrics.csv     per episode: reward, distance, crashes, steps survived
  checkpoints/    e.g. ep1000.pt, ep5000.pt, best.pt
  replays/        recordings of each new best episode (JSON Lines)
  notes.md        your observations
```

- Runs can be listed, compared (learning curves on one chart), replayed, and reproduced with the same seed.
- Expected sizes, as ESTIMATES: model files KB to a few MB, replays a few KB each.

### 5. Agent and training

- A torch neural network drives the car through the env, and learns by trial and error over many episodes.
- **Output of training:** model weights (`.pt`), config, metrics, replays, all in the run folder.
- **Pause in place:** training stops between episodes and stays in memory. While paused, you can watch replays or load the current weights into live play. Resume continues exactly.
- **Stop and resume later:** save a checkpoint, exit, and resume from it any time.
- **A full checkpoint holds:**

  | Item | Why |
  |---|---|
  | Model weights | The learned behavior |
  | Optimizer state | Avoids a learning stutter after resume |
  | Episode/step counters, best score | Keeps metrics and replays continuous |
  | Random number generator states | Makes a resumed run identical to an uninterrupted one |
  | Replay buffer (DQN only, optional) | The agent's past experience. Can be tens to hundreds of MB |

- **Branch:** resume an old checkpoint with a changed setting as a new run, then compare.

### 6. Control center GUI

Separate windows, **one process per window**:

```
Control center window        Simulation window 1      Simulation window 2
(runs, curves, console)      (live play: you + AI)    (replay of run B)
        │                           ▲                        ▲
        └──── commands / metrics ───┴────────────────────────┘
                        (IPC: inter-process communication)
```

- **Control center:** runs list and status, learning curves, and a terminal-style console (scrolling log + command line). Example commands: `train`, `pause`, `resume`, `replay`, `spawn`, `join`, `compare`, `open`.
- **Simulation windows:** each runs its own `World` + `Renderer`, for live play or a replay. Any number can be open side by side.
- **Training runs headless in background processes**, at full speed, with no window. The control center shows their live metrics and logs.
- **Live play:** trained agents (loaded from `.pt`) drive at normal speed. It only runs agents, it doesn't train them, so it's cheap.
- **IPC:** commands go from the control center to the other processes, and metrics and logs come back. Candidates: `multiprocessing` queues, or a local socket.
- **Why separate processes:** standard pygame gives one window per process. pygame-ce's multi-window API is NOT VERIFIED. Separate processes also mean a crashed or closed simulation window doesn't stop the control center or training.
- UI library candidate: `pygame_gui`. NOT YET CHECKED FOR PYGAME-CE COMPATIBILITY.
- The control center layout and console could land earlier, to help watch steps 3 to 5.
- Cost: the IPC layer is extra work, compared to a single window.

### 7. Multiple cars

- Every car takes its `ActionInput` from a controller: keyboard (you), a trained agent, or a replay.
- **Ghost mode:** several cars in one world that pass through each other, so you can drive among agents early.
- Then the polygon hitbox ([decision 004](decisions/004-polygon-hitbox-deferred.md)) and car-vs-car collision in the `World`.
- Then competition: agents learning against each other (multi-agent RL).

## Open questions

- **Game goal**, which decides the step 3 reward and maze design. Options: navigation (reach the exit of an unseen maze), racing (lap time), competition (beat other agents), or an open sandbox.
- **Experiments to run** (ideas so far): reward design, number of rays, network size, algorithm (DQN vs PPO), generalization to unseen mazes, and spotting reward loopholes (like spinning in place to avoid crashes).

## Refactor scope (step 2, done)

In scope:
- A small in-house ECS core (entities, components, systems, resources)
- Replacing `StateSingleton`/`FieldSingleton` and global `FLAGS` reads with per-world resources
- Moving the car state into components, and the car logic into steering, movement, and sensor systems
- Moving drawing into a render system, separate from the simulation step

Out of scope: any behavior change. The demo must look and drive the same, as the step 1 tests check. That includes keeping the current `Rect` hitbox.

## Target layout

Layers: [decision 002](decisions/002-sim-render-split.md). ECS structure and component and system mapping: [decision 005](decisions/005-entity-component-system.md).
