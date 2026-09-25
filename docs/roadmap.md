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
| 3a | Simulation window UI: bigger window, top bar, right info panel, bottom event strip, readable labels, game leaderboard slot. Field size decoupled from the window | Done |
| 3b | Realistic controls: momentum and drag, SPACE brake, S brakes then reverses, speed-based turning. Later calibrated for human play, plus a steering wheel ramp | Done |
| 3c | Fixed-timestep clock: simulation at a fixed 120 steps/s, drawing at the auto-detected display rate with vsync, interpolated car drawing ([decision 008](decisions/008-fixed-timestep-clock.md)) | Done |
| 3d | Polygon hitbox (the car's real 4 corners) and float center position. The car still stops at the border until 3f | Done |
| 3e | 8 rays around the car, starting at the car's body edge | Done |
| 3f | Round timer (60 s = 7,200 steps at 120 steps/s) and crash = game over | Done |
| 3g | Rewards (+1 per 10 px forward) and checkpoints (+100, seeded random spawns) | Done |
| 3h | Env API for agents: observation (`get_state`: rays, speed, steering, checkpoint compass, time left), reward, game over, 5-bool action | Next |
| 4 | Replay and experiment runs: headless episodes, recordings of new bests, replay mode, one folder per run | Planned |
| 5 | Agent and training: torch model, training loop, full checkpoints, pause / resume / branch, evaluation suite (box-map skills). **Milestone: the first skilled agent** | Planned |
| 6 | Control center GUI: its own window (runs panel, learning curves, terminal-style console, agent roster grid, agent profile pages, agent leaderboard), plus separate simulation windows for live play and replays | Planned |
| 7 | Maps: map files, inner walls (rectangles), map editor. Evaluation suite gains map-based skills (corridors, unseen maps) | Planned |
| 8 | Multiple cars and local multiplayer: game setup lobby (pick agents and human players), keyboard and gamepad controllers, ghost mode first (no car-vs-car collision), then car-vs-car collision (SAT), then angled (line segment) walls, then competition. Game leaderboard fully used | Planned |
| 9 | Fuel system: limited capacity, fuel spawns, observation adds fuel level and the nearest K fuels | Planned |
| 10 | Parallel environments for faster training, with a live grid view and spectate mode | Planned |
| Later | Multiple rounds per game, online multiplayer, weapons and skills | Idea |

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
│                 FIELD                        │ SENSORS: distance   │
│           (same size as today)               │  per ray (8 rays)   │
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
- **Readable labels:** `SPD`/`ACC`/`AGL`/`LSC`/`FSC` become "Speed (px/s)", "Pedal", "Heading", and named sensor distances.
- **Warning colors** (added after 3e): amber = caution, red = danger, on both label and value.

  | Row | Amber | Red |
  |---|---|---|
  | **Every ray** (proximity) | Under 40 px | Under 15 px |
  | Rays on the travel path (front three forward, back three reversing) | Below 2× stopping distance | Below stopping distance |
  | Speed | | Too fast to stop before the wall ahead |
  | Status (top bar) | STOPPED | |
  | FPS (bottom bar) | Below 90 % of target | Below 50 % |
  | Time left (top bar) | Under 10 s | Under 5 s |

  The ray lines in the field use the same levels: **muted gray when safe**, amber and red otherwise, with warning rays drawn on top (`warnings.ray_levels` is shared by panel and field). The hitbox outline stays white. Each ray shows the more severe of its two rules.

  A "Stop dist" row shows the current stopping distance (reaction + braking; 150 px at max speed). Time left and the red "CRASHED" status arrived with 3f. The checkpoint distance turns green when close (3g). Planned: agent inputs at their extremes highlighted (step 5).
- **Retro style** (changed after 3a): panels use only lines and text, with colors and bold for distinction. The sensor radar and filled boxes were removed. Graphics belong inside the field.
- **Game leaderboard slot:** ranks cars in the current game by score. Built as a panel section now, and it fills in once there are several cars (step 8) or parallel games (step 10).
- **H** shows and hides the debug lines in the field: rays, hitbox, and future distance or boundary lines. The panels always stay visible.
- **Field size gets its own config**, decoupled from the window (today it's calculated from the window size). It stays 855×480, so the physics doesn't change. Behavior tests must still pass unchanged in this sub-step.

### 3c. Fixed-timestep clock

Details and reasons: [decision 008](decisions/008-fixed-timestep-clock.md).

- The simulation always runs at **120 steps/s**, identical on every machine and headless.
- Drawing runs at the **auto-detected display refresh rate** (vsync where available), or a configured override.
- Each drawn frame runs 0, 1, or 2 simulation steps, based on real time elapsed. Real time only decides how many steps run, never what a step does.
- Cars are drawn **interpolated** between their previous and current step positions, for smooth motion at any display rate.
- Changing from 90 to 120 steps/s changes the per-step physics, so fixtures get regenerated. The driving feel in seconds stays the same.

### 3d. Polygon hitbox

Why before crashes: with the old growing box, "touching the border = game over" would end the round while a diagonal car is visibly still pixels away. That's unfair to a human driver, and it teaches agents the wrong safety margins.

- The hitbox is the car's **4 real corners**, rotating with it. See [decision 004](decisions/004-polygon-hitbox-deferred.md).
- **Position becomes a float center point**, replacing the integer `Rect` plus the `x_float`/`y_float` carry.
- **Border check in the box map:** the car touches the border exactly when one of its corners leaves the field. The field is a convex rectangle, so this is exact.
- The rays in 3e start at the body edge of this polygon.
- SAT (Separating Axis Theorem) is added later, for inner walls (step 7) and car-vs-car collision (step 8), using this polygon.
- `rotated_bounds` was removed, together with the integer-rect movement helpers.
- **Exact contact:** moves go as far as possible until a corner touches the border, instead of stopping up to a step short. Turns into the border are cancelled.
- The start position became exactly a quarter of the field's width, mid height, dropping the old truncation quirk.

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
- **Action repeat:** the agent decides every 4 simulation steps (**30 decisions/s** at 120 steps/s) and holds its action in between. That keeps a 60 s round at 1,800 decisions instead of 7,200, which makes learning easier. See [decision 008](decisions/008-fixed-timestep-clock.md).

#### Evaluation suite

Beyond training time, an agent's skill depends mostly on what it was trained on: training environments (the biggest factor), reward design, observation, algorithm, network size, and seed. Training on one map makes a **specialist**. Training on many varied or randomized maps makes a **generalist**.

To compare agents fairly, every agent runs the same **fixed evaluation suite**: test scenarios that never change, with fixed seeds, averaged over several episodes. Each scenario measures one skill:

| Skill | Measured by | Available from |
|---|---|---|
| Survival | Share of the round survived | Step 5 |
| Checkpoint hunting | Checkpoints per minute | Step 5 |
| Braking | Stopping before walls at high speed | Step 5 |
| Wall control | Survival in narrow corridors | Step 7 (needs inner walls) |
| Generalization | Score on maps it has never trained on | Step 7 (needs map files) |

- The suite runs automatically at each saved checkpoint, so skill history builds up over training.
- Changing a scenario creates a new suite version, and scores from different versions are never mixed.

#### Agent history and storage

Goal: keep as much history per agent as possible, while files stay small and cheap to review. **Layered storage:** every event is kept, each layer only as detailed as needed.

```
agents/<agent_id>/
  profile.json      ~2 KB          current skills, lineage summary, totals. Read this first
  history.jsonl     ~200 B/event   one line per event, append-only
  checkpoints/      milestone weights only
runs/<run_id>/      per-episode detail (step 4)
```

| Layer | Holds | Kept |
|---|---|---|
| `profile.json` | Current skill scores, lineage summary, total episodes and training time, observation layout version | Always, rewritten on each change |
| `history.jsonl` | **Events, not episodes:** training phase started/ended, checkpoint saved, evaluation results, branch, settings change. Plus a summary every 100 episodes (mean/min/max reward, checkpoints, crash rate) | Forever |
| Run folder `metrics.csv` | Every single episode | Forever. Plain numbers that compress well |
| Checkpoints | Milestones only: best, latest, every Nth, and any branch point | A retention policy prunes the rest |
| Replays | New bests and evaluation episodes only, gzipped | Forever |

- Rough sizes (ESTIMATES, NOT MEASURED): 1,000 history events ≈ 200 KB. A checkpoint with optimizer state ≈ 60 KB (about 5,000 network parameters), so 50 milestones ≈ 3 MB per agent.
- **Token-efficient review:** read `profile.json` first, then only the relevant history lines. Per-episode CSVs only when needed.
- An `agent summary <id>` command prints a compact digest (lineage, skills, trend) for both humans and Claude.

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
- **Agent roster:** agents as cards in a grid: name, mini skill radar, evaluation score, specialty (for example "box specialist"), training summary. Sort and filter by score, skill, map, or date, with a table view toggle for comparing many. Clicking a card opens its profile page.
- **Agent profile page:**
  - **Lineage:** initial training environment, then every later training phase (maps, episodes, which checkpoint it branched from).
  - **Skill radar chart:** one axis per skill from the evaluation suite, showing current levels.
  - **Skill history:** scores at each checkpoint, so you see skills grow, and sometimes drop. Further training on new environments can make an agent forget old skills ("catastrophic forgetting"), and this view reveals it.
- **Agent leaderboard:** agents ranked by **evaluation suite score**, the fair comparison (same scenarios, same seeds), plus all-time high scores per map. Training scores aren't used for ranking, because random seeds and maps make some episodes easier than others.
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

### 8. Multiple cars and local multiplayer

- Every car takes its `ActionInput` from a controller: keyboard, gamepad, a trained agent, or a replay.
- **Game setup lobby:** pick the map and number of rounds, add agents from the roster, add human slots, then start (a simulation window opens). Setups can be saved as presets (for example "me vs top 3 agents").
- **Local input devices** (on the same computer, including Bluetooth gamepads):
  - Keyboard split for 2 players: WASD + Space, and arrows + Right Shift.
  - Gamepads through pygame-ce's controller support: stick to steer, triggers for gas and brake. Analog input is converted to the 5 on/off actions with thresholds. Analog actions for agents could be a later experiment.
  - "Press a button to join" assigns each device to a slot in the lobby.
- **Online-ready design** (online itself comes later): see [decision 007](decisions/007-local-multiplayer-online-ready.md).
- **Ghost mode:** several cars in one world that pass through each other, so you can drive among agents early.
- Then car-vs-car collision in the `World`: SAT on the polygon hitboxes from step 3d ([decision 004](decisions/004-polygon-hitbox-deferred.md)).
- Then competition: agents learning against each other (multi-agent RL).
- The game leaderboard (slot from step 3a) ranks the cars live.

### 10. Parallel environments

One network (one set of weights) drives N copies of the environment at once, one per process. The agent doesn't learn N times over: it **collects N times more experience per second** and learns from all of it together.

1. All envs send observations, and the network decides all actions **in one batched pass**.
2. Each env steps its own car, in its own process.
3. Results from every env go into one shared pool.
4. The network updates its weights from the pooled experience.
5. Every env uses the updated weights on its next step.

- **Synchronous** (all envs step in lockstep): the choice here, since determinism matters for replays.
- **Speed-up** as an ESTIMATE: about 5 to 8 times on the 10-core M5, not the full core count, because the learning update doesn't parallelize and inter-process messaging has overhead.
- Mixed situations across envs (different seeds and checkpoint spawns) also make learning more stable.

**Watching parallel training** (a toggle, since it adds a little overhead):
- **Live grid:** a window with one small view per env. Workers send lightweight snapshots (car position and angle, checkpoint, score) every few steps, and the GUI process draws them. Workers never render. Cars look sped up, since training runs faster than real time.
- **Spectate one:** click a tile to enlarge that env's game, with its full info panel.
- The game leaderboard ranks the parallel games by score.

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
