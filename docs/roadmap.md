# Roadmap

Goal: train real RL agents in a 2D car game, watch how they learn, run experiments on them, and play alongside them. Game rules: [game design](game-design.md).

**First goal (steps 3 to 6):** system basics. One car in the box map, a skilled agent that survives the whole round while driving and collecting checkpoints, agent management, then the control center.

## Step order

| # | Step | Status |
|---|---|---|
| 1 | Behavior tests that pin down current car physics (the refactor safety net, later the determinism test) | Done |
| 2 | Refactor into ECS: sim/render split, remove singletons and global `FLAGS` reads. **Structure only** | Done |
| 2a | ECS core (`src/ecs/`): World, entities, components, resources, systems, with unit tests | Done |
| 2b | Car components, systems (steering, movement, sensors), and factories in `src/sim/`. Behavior tests run against both old and new code | Done |
| 2c | Render system, then switch the demo and env to the ECS. Removed the legacy test runner, since it needed the old env | Done |
| 2d | Delete the old singletons, models, and sprites (dead code since 2c), and rewrite `architecture.md` | Done |
| **3** | **First game rules in the box map** ([game design](game-design.md#first-goal-roadmap-step-3)). Intended behavior changes, so fixtures get regenerated | Next |
| 3a | Simulation window UI: bigger window, top bar, right info panel, bottom event strip, readable labels. Field size decoupled from the window | Next |
| 3b | Realistic controls: momentum and drag, SPACE brake, S brakes then reverses, speed-based turning | Planned |
| 3c | Polygon hitbox (the car's real 4 corners) and float center position. The car still stops at the border until 3e | Planned |
| 3d | 8 rays around the car, starting at the car's body edge | Planned |
| 3e | Round timer (60 s = 5,400 steps) and crash = game over | Planned |
| 3f | Rewards (+1 per 10 px forward) and checkpoints (+100, seeded random spawns) | Planned |
| 3g | Env API for agents: observation (`get_state`: rays, speed, checkpoint compass, time left), reward, game over, 5-bool action | Planned |
| 4 | Replay and experiment runs: headless episodes, recordings of new bests, replay mode, one folder per run | Planned |
| 5 | Agent and training: torch model, training loop, full checkpoints, pause / resume / branch. **Milestone: the first skilled agent** | Planned |
| 6 | Control center GUI: its own window (runs panel, learning curves, terminal-style console), plus separate simulation windows for live play and replays | Planned |
| 7 | Maps: map files, inner walls (rectangles), map editor | Planned |
| 8 | Multiple cars: ghost mode first (you join agents, no car-vs-car collision), then car-vs-car collision (SAT), then angled (line segment) walls, then competition | Planned |
| 9 | Fuel system: limited capacity, fuel spawns, observation adds fuel level and the nearest K fuels | Planned |
| 10 | Parallel environments for faster training | Planned |
| Later | Multiple rounds per game, weapons and skills | Idea |

## Step details

### 3. First game rules in the box map

The rules and values are in [game design](game-design.md#first-goal-roadmap-step-3). Build notes:

- Each sub-step changes behavior on purpose. Regenerate the fixtures (`python -m tests.generate_behavior_fixtures`) and add scenarios for the new behavior, for example tapping vs holding the brake, coasting to a stop, and a crash.
- The round timer and checkpoint random number generator are world resources, seeded per round. Timer and randomness stay deterministic ([conventions](conventions.md#determinism-must-keep)).
- New config keys (all values tunable): reward distance, checkpoint radius and margins, drag, brake strength, `round.seconds`, `game.rounds`.
- The HUD shows the remaining time, score, and 8 ray distances.
- Observation layout: [game design](game-design.md#observation-what-the-agent-sees). Normalize every input, and keep the layout in one place so the agent and replays agree on it.

### 3a. Simulation window UI

```
┌──────────────────────────────────────────────┬─────────────────────┐
│ ROUND 1/1  TIME 00:42.3  SCORE 1,240  ● DRIVING │ CAR                 │
│ DRIVER: You (keyboard)                       │  Speed, Throttle,   │
├──────────────────────────────────────────────┤  Heading, Position, │
│                                              │  Inputs [W]A S D ␣  │
│                                              ├─────────────────────┤
│                 FIELD                        │ SENSORS: radar of   │
│           (same size as today)               │  8 rays + distances │
│                                              ├─────────────────────┤
│                                              │ OBJECTIVE: checkpoint│
│                                              │  distance, direction│
│                                              ├─────────────────────┤
│                                              │ REWARD: distance,   │
│                                              │  checkpoints, last  │
│                                              ├─────────────────────┤
│                                              │ AGENT VIEW: inputs  │
│                                              │  as bars, action    │
├──────────────────────────────────────────────┴─────────────────────┤
│ event log (checkpoints, crash)          Step 3,812/5,400   FPS 90  │
└────────────────────────────────────────────────────────────────────┘
```

- **Top bar:** what you glance at most: round, time, score, status, who's driving.
- **Right panel:** detail grouped by topic. Each later sub-step fills in its own section (timer, rewards, checkpoint, agent view).
- **Bottom strip:** event log, step counter, FPS.
- **Readable labels:** `SPD`/`ACC`/`AGL`/`LSC`/`FSC` become "Speed (px/s)", "Throttle", "Heading", and a labeled radar diagram.
- **Hotkey** (for example H) hides and shows the panels.
- **Field size gets its own config**, decoupled from the window (today it's calculated from the window size). It stays 855×480, so the physics doesn't change. Behavior tests must still pass unchanged in this sub-step.

### 3c. Polygon hitbox

Why before crashes: with the old growing box, "touching the border = game over" would end the round while a diagonal car is visibly still pixels away. That's unfair to a human driver, and it teaches agents the wrong safety margins.

- The hitbox is the car's **4 real corners**, rotating with it. See [decision 004](decisions/004-polygon-hitbox-deferred.md).
- **Position becomes a float center point**, replacing the integer `Rect` plus the `x_float`/`y_float` carry.
- **Border check in the box map:** the car touches the border exactly when one of its corners leaves the field. The field is a convex rectangle, so this is exact.
- The rays in 3d start at the body edge of this polygon.
- SAT (Separating Axis Theorem) is added later, for inner walls (step 7) and car-vs-car collision (step 8), using this polygon.
- `rotated_bounds` (`src/sim/geometry.py`) is no longer used by the physics.

### 4. Replay and experiment runs

Replays: see [decision 003](decisions/003-replay-over-multi-window.md).

Each training run gets its own folder:

```
runs/<date>_<name>_seed<N>/
  config.json     all settings: reward, sensors, network, learning rate, seed
  metrics.csv     per episode: reward, distance, checkpoints, crashes, steps survived
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

### 7. Maps

A map is a JSON file in `maps/`:

```json
{
  "name": "s_curve",
  "size": [855, 480],
  "walls": [[100, 0, 20, 300], [300, 180, 20, 300]],
  "spawns": [{"x": 50, "y": 240, "angle": 0}]
}
```

- Walls are **axis-aligned rectangles** `[x, y, width, height]` for now: see [decision 006](decisions/006-rectangle-walls-first.md).
- `load_map(world, path)` turns walls and spawns into entities. Checkpoints keep spawning randomly, and must avoid walls.
- Each run's `config.json` records the map name plus a content hash, so experiments and replays point at the exact layout.
- **Map editor**, a simulation window mode:
  - Click and drag to draw walls, with snap-to-grid.
  - Place spawn points (with direction).
  - Select, move, delete, undo.
  - Save and load files in `maps/`.
  - **Test drive:** switch to live play on the map being edited, then back.

### 8. Multiple cars

- Every car takes its `ActionInput` from a controller: keyboard (you), a trained agent, or a replay.
- **Ghost mode:** several cars in one world that pass through each other, so you can drive among agents early.
- Then car-vs-car collision in the `World`: SAT on the polygon hitboxes from step 3c ([decision 004](decisions/004-polygon-hitbox-deferred.md)).
- Then competition: agents learning against each other (multi-agent RL).

## Open questions

- **Experiments to run** (ideas so far): reward design, number of rays, network size, algorithm (DQN vs PPO), generalization to unseen maps, spotting reward loopholes (like circling forever for distance points), and **compass vs sensor-only agents** (rays that also detect checkpoints and fuel, with no compass: more realistic, slower to learn).

## Refactor scope (step 2, done)

In scope:
- A small in-house ECS core (entities, components, systems, resources)
- Replacing `StateSingleton`/`FieldSingleton` and global `FLAGS` reads with per-world resources
- Moving the car state into components, and the car logic into steering, movement, and sensor systems
- Moving drawing into a render system, separate from the simulation step

Out of scope: any behavior change. The demo must look and drive the same, as the step 1 tests check. That includes keeping the current `Rect` hitbox.

## Target layout

Layers: [decision 002](decisions/002-sim-render-split.md). ECS structure and component and system mapping: [decision 005](decisions/005-entity-component-system.md).
