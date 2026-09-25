# Roadmap

Goal: train real RL agents in a 2D car game, watch how they learn, run experiments on them, and play alongside them. Game rules: [game design](game-design.md).

**First goal (steps 3 to 6):** system basics. One car in the box map, a skilled agent (RL or imitation) that survives the whole round while driving and collecting checkpoints, agent management, then the control center.

## Step order

| # | Step | Status |
|---|---|---|
| 1 | Behavior tests that pin down current car physics (the refactor safety net, later the determinism test) | Done |
| 2 | Refactor into ECS: sim/render split, remove singletons and global `FLAGS` reads. **Structure only** | Done |
| 2a | ECS core (`src/ecs/`): World, entities, components, resources, systems, with unit tests | Done |
| 2b | Car components, systems (steering, movement, sensors), and factories in `src/sim/`. Behavior tests run against both old and new code | Done |
| 2c | Render system, then switch the demo and env to the ECS. Removed the legacy test runner, since it needed the old env | Done |
| 2d | Delete the old singletons, models, and sprites (dead code since 2c), and rewrite `architecture.md` | Done |
| **3** | **First game rules in the box map** ([game design](game-design.md#first-goal-roadmap-step-3)). Intended behavior changes, so fixtures get regenerated | Done |
| 3a | Simulation window UI: bigger window, top bar, right info panel, bottom event strip, readable labels, game leaderboard slot. Field size decoupled from the window | Done |
| 3b | Realistic controls: momentum and drag, SPACE brake, S brakes then reverses, speed-based turning. Later calibrated for human play, plus a steering wheel ramp | Done |
| 3c | Fixed-timestep clock: simulation at a fixed 120 steps/s, drawing at the auto-detected display rate with vsync, interpolated car drawing ([decision 008](decisions/008-fixed-timestep-clock.md)) | Done |
| 3d | Polygon hitbox (the car's real 4 corners) and float center position. The car still stops at the border until 3f | Done |
| 3e | 8 rays around the car, starting at the car's body edge | Done |
| 3f | Round timer (60 s = 7,200 steps at 120 steps/s) and crash = game over | Done |
| 3g | Rewards (+1 per 10 px forward) and checkpoints (+100, seeded random spawns) | Done |
| 3h | Env API for agents: observation (`get_state`: rays, speed, steering, checkpoint compass, time left), reward, game over, 5-bool action | Done |
| **4** | **Stages, replays, and experiment runs** | Next |
| 4a | **Groundwork (urgent, before any file format):** split config into game-defining vs presentation keys, separate the agent reward from the game score, code version stamp ([decision 010](decisions/010-decouple-before-file-formats.md)) | Done |
| 4b | Stage format: the box stage as a file (origin 0,0), loader, spawn schedules (random from seed, or scripted). The stage takes over the game-defining field and checkpoint keys ([decision 009](decisions/009-stage-format-and-spawn-schedules.md)) | Done |
| 4c | **Reward profiles:** agent rewards as weighted terms in `rewards/<name>.json`, separate from the game score ([decision 011](decisions/011-reward-profiles.md)) | Done |
| 4d | Replay format, recorder, and self-verifying replayer (simulation only). Per-slot actions, named actions, driver record (with player), reward profile, code version | Next |
| 4e | Replay mode in the window: pause, 0.5×/1×/2×/4× speed, frame stepping, restart | Planned |
| 4f | Baseline drivers: random and heuristic ("compass driver"), and the one driver interface every driver uses | Planned |
| 4g | Experiment runner: headless episodes, run folder, metrics, best-episode replays. The run config records the reward profile, game-defining config, and code version | Planned |
| 4h | Record your own demo rounds: per player, latest 50 kept, K keeps a run for good | Planned |
| **5** | **Agents** ([decision 012](decisions/012-agent-training-modes.md)) | Planned |
| 5a | RL agent and training: torch model, training loop, full checkpoints, pause / resume / branch, evaluation suite (box-map skills). **Milestone: the first skilled agent** | Planned |
| 5b | Imitation agents: learn from your recorded runs (behavioral cloning), then optionally keep improving with RL | Planned |
| 6 | Control center GUI: its own window (training setup, runs panel, learning curves, terminal-style console, recordings and datasets, agent roster grid, agent profile pages, agent leaderboard), plus separate simulation windows for live play and replays | Planned |
| 7 | Maps: inner walls (rectangles) in stage files, camera for big stages, map editor (walls, spawns, scripted checkpoint sequences). Evaluation suite gains map-based skills (corridors, unseen maps) | Planned |
| 8 | Multiple cars and local multiplayer: game setup lobby (stage, rounds, seed, agents, human players), keyboard and gamepad controllers, ghost mode first (no car-vs-car collision), then car-vs-car collision (SAT), then angled (line segment) walls, then competition. Game leaderboard fully used | Planned |
| 9 | Fuel system: limited capacity, fuel spawns (its own spawn schedule and random stream), observation adds fuel level and the nearest K fuels | Planned |
| 10 | Parallel environments for faster training, with a live grid view and spectate mode | Planned |
| Later | Hazards ([game design](game-design.md#hazards-future)), multiple rounds per game (with per-round state, see [decision 010](decisions/010-decouple-before-file-formats.md)), online multiplayer, weapons and skills | Idea |

## Step details

### 3. First game rules in the box map

The rules and values are in [game design](game-design.md#first-goal-roadmap-step-3). Build notes:

- Each sub-step changes behavior on purpose. Regenerate the fixtures (`python -m tests.generate_behavior_fixtures`) and add scenarios for the new behavior, for example tapping vs holding the brake, coasting to a stop, and a crash.
- The round timer and checkpoint randomness are world resources, seeded per round. Timer and randomness stay deterministic ([conventions](conventions.md#determinism-must-keep)). Since 4b, checkpoints follow the stage's spawn schedule.
- New config keys (all values tunable): reward distance, drag, brake strength, `round.seconds`, `game.rounds`. Checkpoint radius and margins started in config and moved to the stage file in 4b.
- The HUD shows the remaining time, score, and 8 ray distances.
- Observation layout: [game design](game-design.md#observation-what-the-agent-sees). Normalize every input, and keep the layout in one place so the agent and replays agree on it.

### 3a. Simulation window UI

```
┌──────────────────────────────────────────────┬─────────────────────┐
│ ROUND 1/1  TIME 00:42.3  SCORE 1,240 DRIVING │ CAR: speed, stop    │
│ DRIVER  STAGE  CHECKPOINTS  SEED  REWARD     │  dist, pedal,       │
├──────────────────────────────────────────────┤  steering, heading, │
│                                              │  position, inputs   │
│                                              ├─────────────────────┤
│                 FIELD                        │ SENSORS: 8 rays     │
│              (the stage)                     ├─────────────────────┤
│                                              │ OBJECTIVE           │
│                                              ├─────────────────────┤
│                                              │ SCORE (game points) │
│                                              ├─────────────────────┤
│                                              │ AGENT REWARD        │
│                                              ├─────────────────────┤
│                                              │ LEADERBOARD         │
├──────────────────────────────────────────────┴─────────────────────┤
│ latest event          Step  SIM 120/s  FPS  R: restart  H: lines   │
└────────────────────────────────────────────────────────────────────┘
```

- **Top bar:** what you glance at most: round, time, score, status, who's driving. Since step 4b also the round's stage (name and size), checkpoint mode, and seed, and since 4c the reward profile, so custom stages, seeds, and profiles are always visible.
- **Right panel:** detail grouped by topic. Each later sub-step filled in its own section. Since 4c, SCORE shows game points and AGENT REWARD shows the reward profile's values. An agent view (observation as bars, chosen action) comes with step 5.
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
- **Field size gets its own config**, decoupled from the window. It stays 855×480, so the physics doesn't change. Behavior tests must still pass unchanged in this sub-step. Since 4b, the size comes from the stage file.

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
- **Exact contact:** moves go as far as possible until a corner touches the border, instead of stopping up to a step short. Turns into the border were cancelled; since 3f, touching the border is a crash.
- The start position became exactly a quarter of the field's width, mid height, dropping the old truncation quirk. Since 4b, it's the stage's spawn.

### 4. Stages, replays, and experiment runs

Goal: run many episodes headless, save each run's results, keep recordings of the best episodes, and play any recording back. No neural network yet: two baseline drivers exercise the pipeline, and become the benchmark trained agents must beat.

#### 4a. Groundwork (urgent)

Fixes to code that already exists, so the file formats in 4b to 4h start clean. Details: [decision 010](decisions/010-decouple-before-file-formats.md).

- **Config split:** **game-defining** keys (driving, rules, rewards, round length, step rate, and later the stage) are saved in replays and runs. **Presentation** keys (`hud`, `display`, `window`, debug lines) are never saved, so tuning the HUD can't make an old replay look "changed". A `game_config()` helper returns only the game-defining part.
- **Agent reward vs game score:** the **game score** stays the HUD and leaderboard value, with fixed rules. The **agent reward** becomes a small reward function of the step's events (points gained, crash, checkpoint, time). The default is "points gained", so nothing changes yet, but step 5 can experiment with rewards without touching the game. **Extended in 4c into reward profiles.**
- **Code version stamp:** a helper returns the git commit, plus "dirty" when there are uncommitted changes. Replays and runs record it.

#### 4b. Stage format

Details: [decision 009](decisions/009-stage-format-and-spawn-schedules.md).

- A **stage file** defines the whole playing area: size, walls (empty for now), car spawns, and spawn schedules. The box stage becomes `stages/box.json`.
- **Origin at (0, 0)**, dropping the leftover (22.5, 97.5) offset. Physics distances don't change, positions shift, so fixtures are regenerated once.
- A `format` version lets future stages add fields (segment walls, zones, themes) without breaking old ones. The size isn't fixed: bigger stages get a camera in step 7.
- **Spawn schedules:** stage + seed decide every spawn, independent of the driving, so every driver plays the exact same round.
  - `random` mode: the seed generates the sequence up front, with backup candidates per slot for when a spot is too close to a car.
  - `scripted` mode: the stage lists exact spots (and later, timings for fuel).
  - Each spawner (checkpoints now, fuel later) has its own random stream derived from the seed, so adding one never changes another's sequence.

#### 4c. Reward profiles

Details: [decision 011](decisions/011-reward-profiles.md).

- The agent reward is a **weighted sum of terms**, defined in a profile file: `rewards/<name>.json`, starting with `rewards/default.json` (points only, today's reward).
- Terms are things measurable in one step: points, checkpoints, crashed, time up, per step, distance moved, speed, steering change, closest wall.
- Unknown terms or a wrong format fail early with a clear error. New terms can be added later without breaking old profiles.
- **The game score is never affected**, so agents trained with different profiles still compete on the same leaderboard.
- The env takes a profile by name or path. Replays (4d) and runs (4g) record the profile used, and agent profiles (step 5) show "trained with".
- Profiles have a `name` and an optional `description`. The window shows the profile name in the top bar, and the agent reward (last step, this game) in the side panel, also while a human drives.

#### 4d. Replay format

Details: [decision 003](decisions/003-replay-over-multi-window.md).

- **Inputs, not positions:** a header (format version, stage **embedded in full**, seed, game-defining config, reward profile, observation version, drivers) plus the actions, re-simulated on playback.
- **Per simulation step**, storing only changes ("from step 1,834: gas + left"). A full 60 s round is a few KB.
- **Self-verifying:** the file stores the final score and step. A mismatch on playback means the simulation changed since recording, and the replay is flagged instead of silently showing wrong driving.
- JSON Lines, readable as text.
- **Per-slot actions:** every action line is keyed by slot (`{"step": 1834, "actions": {"1": [...]}}`), and the header lists the slots and their drivers. Multi-car replays (step 8) then need no format change.
- **Named actions:** the header stores `action_names`, and actions are read by name. Actions added later (weapons, skills) count as "not pressed" in old replays.
- **Driver record:** `{"type": "human", "player": "zen", "device": "keyboard"}` or `{"type": "agent", "id": ..., "checkpoint": ...}`, not just a label. The **player** name groups a person's runs into an imitation dataset (5b).
- **Code version** in the header, so an out-of-date replay shows when the simulation changed.

#### 4e. Replay mode

- `python app.py -replay <file>` opens a simulation window playing the recording.
- Controls: pause, speed 0.5× / 1× / 2× / 4×, step one frame, restart. The HUD shows "REPLAY", and the top bar shows the replay's driver, stage, seed, and reward profile as usual.
- An out-of-date replay (its end line doesn't match on re-simulation) is flagged in the window.

#### 4f. Baseline drivers

- **Random:** random actions, the floor.
- **Heuristic ("compass driver"):** hand-written rules: steer toward the checkpoint using the compass inputs, brake when a travel-path ray is short.
- Both use only the env API (observation in, action out), exactly like a trained agent will.
- **One driver interface** for every driver: observation in, action out. Random, heuristic, RL agents (5a), and imitation agents (5b) all plug in the same way, so nothing downstream (runner, replays, evaluation, live play) needs special cases.

#### 4g. Experiment runner

- `python app.py -run <name> --driver heuristic --reward default --stage box --episodes 200`, headless at full speed.
- Each run gets its own folder in `runs/`, which is **gitignored** (results are local data):

```
runs/<date>_<name>_seed<N>/
  config.json     all settings: stage, rewards, driver, seeds, versions
  metrics.csv     one row per episode: seed, steps, score, distance points,
                  checkpoints, agent reward total, how it ended
  replays/        recordings of each new best episode
  checkpoints/    model files, from step 5a (ep1000.pt, best.pt, ...)
  notes.md        your observations
```

- Runs can be listed, compared (learning curves on one chart), replayed, and reproduced with the same seed.
- `config.json` records the **reward profile** used (name and full content), the **game-defining config**, and the **code version**.
- Expected sizes, as ESTIMATES: replays a few KB each, model files KB to a few MB.

#### 4h. Record your own demo rounds

- Every round you play in the demo is saved as a replay, **on by default**, keeping the **latest 50**.
- Recordings are stored **per player** (`recordings/<player>/`).
- **Keep a run:** a key after the round (for example K) marks it kept. Kept runs are never removed by the latest-50 limit, and they're the natural dataset for an imitation agent (5b).
- Replay your own rounds, and later compare them with agents on the same stage + seed.

### 5. Agents

How agents are trained is flexible: imitation only, RL only, or both in either order. See [decision 012](decisions/012-agent-training-modes.md).

#### 5a. RL agent and training

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
  | Replay buffer (only for value-based algorithms like DQN, optional) | The agent's past experience. Can be tens to hundreds of MB. PPO, recommended in [decision 012](decisions/012-agent-training-modes.md), doesn't need one |

- **Branch:** resume an old checkpoint with a changed setting as a new run, then compare.
- **Observation spec:** the observation becomes configurable per run (number of rays, compass vs sensor-only), recorded in the run config together with its version. See [decision 010](decisions/010-decouple-before-file-formats.md).
- **Reward profiles:** experiments swap the reward profile (from 4c), never the game score. The agent profile page shows which profile trained the agent.
- **Action set covers human inputs:** 12 canonical actions (steering left/none/right × pedal none/gas/reverse/brake) express every one of the 32 key combinations exactly, because the simulation resolves input priorities. Recorded runs can then be learned exactly in 5b.
- **One network shape for both modes:** the policy network must accept imitation training and RL training alike, so a clone's weights can start an RL run. See [decision 012](decisions/012-agent-training-modes.md) (algorithm note).
- **Action repeat:** the agent decides every 4 simulation steps (**30 decisions/s** at 120 steps/s) and holds its action in between. That keeps a 60 s round at 1,800 decisions instead of 7,200, which makes learning easier. See [decision 008](decisions/008-fixed-timestep-clock.md).

#### Evaluation suite

Beyond training time, an agent's skill depends mostly on what it was trained on: training environments (the biggest factor), reward design, observation, algorithm, network size, and seed. Training on one map makes a **specialist**. Training on many varied or randomized maps makes a **generalist**.

To compare agents fairly, every agent runs the same **fixed evaluation suite**: test scenarios that never change, with fixed seeds, averaged over several episodes. Each scenario measures one skill:

| Skill | Measured by | Available from |
|---|---|---|
| Survival | Share of the round survived | Step 5a |
| Checkpoint hunting | Checkpoints per minute | Step 5a |
| Braking | Stopping before walls at high speed | Step 5a |
| Wall control | Survival in narrow corridors | Step 7 (needs inner walls) |
| Generalization | Score on stages it has never trained on | Step 7 (needs more stages, with walls) |

- The suite runs automatically at each saved checkpoint, so skill history builds up over training.
- Changing a scenario creates a new suite version, and scores from different versions are never mixed.

#### Agent history and storage

Goal: keep as much history per agent as possible, while files stay small and cheap to review. **Layered storage:** every event is kept, each layer only as detailed as needed.

```
agents/<agent_id>/
  profile.json      ~2 KB          current skills, lineage summary, totals. Read this first
  history.jsonl     ~200 B/event   one line per event, append-only
  checkpoints/      milestone weights only
runs/<run_id>/      per-episode detail (step 4g)
```

| Layer | Holds | Kept |
|---|---|---|
| `profile.json` | Current skill scores, lineage summary (training phases: imitation datasets and RL reward profiles), total episodes and training time, observation layout version | Always, rewritten on each change |
| `history.jsonl` | **Events, not episodes:** training phase started/ended, checkpoint saved, evaluation results, branch, settings change. Plus a summary every 100 episodes (mean/min/max reward, checkpoints, crash rate) | Forever |
| Run folder `metrics.csv` | Every single episode | Forever. Plain numbers that compress well |
| Checkpoints | Milestones only: best, latest, every Nth, and any branch point | A retention policy prunes the rest |
| Replays | New bests and evaluation episodes only, gzipped | Forever |

- Rough sizes (ESTIMATES, NOT MEASURED): 1,000 history events ≈ 200 KB. A checkpoint with optimizer state ≈ 60 KB (about 5,000 network parameters), so 50 milestones ≈ 3 MB per agent.
- **Token-efficient review:** read `profile.json` first, then only the relevant history lines. Per-episode CSVs only when needed.
- An `agent summary <id>` command prints a compact digest (lineage, skills, trend) for both humans and Claude.

#### 5b. Imitation agents

Learn to drive like a player from their recorded runs (**behavioral cloning**, a form of imitation learning).

1. **Record:** play N rounds, and keep the good ones (4h).
2. **Build a dataset:** re-simulate each kept replay (deterministic) and collect pairs of **observation → the player's action**. Replays don't store observations; re-simulation regenerates them exactly. A 60 s round gives 7,200 pairs.
3. **Train:** supervised learning, predicting the player's action from the observation.
4. **Test:** the clone is a driver like any other: watch it in replays and live play, and score it with the evaluation suite.

**Training modes** (any mix, in any order, recorded in the agent's lineage):
- **Imitation only:** a pure clone of the player.
- **Imitation, then RL:** start from the clone, then keep improving with a reward profile ("start from how I drive, then get better than me"). This usually learns much faster than starting from random.
- **RL, then imitation:** nudge an RL agent toward a player's style.
- **Branch** at any checkpoint to try another mode, and compare.

**Worth knowing:** clones copy mistakes too, and can drift into situations the player never recorded, because small errors compound. More varied runs help, and so does RL fine-tuning.

**Agent profile page:** shows "cloned from: zen, 20 runs", followed by any RL phases and their reward profiles.

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
- **Training setup:** pick the training mode (imitation, RL, or both, [decision 012](decisions/012-agent-training-modes.md)), stage, reward profile, seed or seed range, and driver or starting checkpoint, then start. It's a front end over the runner (4g): the same settings a command line run takes.
- **Recordings and datasets:** browse recordings per player (4h), replay them, keep or unkeep runs, and pick kept runs as an imitation dataset (5b).
- **Everything is a named file** (stages, reward profiles, recordings, runs, agents), so the control center lists and picks them rather than holding its own copies.
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

A map is a **stage file** in `stages/` (format from step 4b). This step fills in its walls:

```json
{
  "format": 1,
  "name": "s_curve",
  "size": [855, 480],
  "walls": [[100, 0, 20, 300], [300, 180, 20, 300]],
  "spawns": [{"x": 50, "y": 240, "angle": 0}],
  "checkpoints": {"mode": "scripted", "radius": 15, "points": [[200, 60], [700, 400]]}
}
```

- Walls are **axis-aligned rectangles** `[x, y, width, height]` for now: see [decision 006](decisions/006-rectangle-walls-first.md).
- **Camera** for stages bigger than the window: zoom-to-fit or following the car.
- The stage loader (`load_stage`) turns walls into entities too. Random spawn schedules must avoid walls, and rays and crashes check walls with the same exact math as the border.
- Replays embed the full stage and runs record it (4d, 4g), so experiments always point at the exact layout.
- **Map editor**, a simulation window mode:
  - Click and drag to draw walls, with snap-to-grid.
  - Place spawn points (with direction).
  - Place scripted checkpoint sequences (points in order), or choose random spawning with margins.
  - Select, move, delete, undo.
  - Save and load stage files in `stages/`.
  - **Test drive:** switch to live play on the map being edited, then back.

### 8. Multiple cars and local multiplayer

- Every car takes its `ActionInput` from a controller: keyboard, gamepad, a trained agent, or a replay.
- **Game setup lobby:** pick the stage, number of rounds, and seed, add agents from the roster, add human slots, then start (a simulation window opens). Setups can be saved as presets (for example "me vs top 3 agents").
- **Local input devices** (on the same computer, including Bluetooth gamepads):
  - Keyboard split for 2 players: WASD + Space, and arrows + Right Shift.
  - Gamepads through pygame-ce's controller support: stick to steer, triggers for gas and brake. Analog input is converted to the 5 on/off actions with thresholds. Analog actions for agents could be a later experiment.
  - "Press a button to join" assigns each device to a slot in the lobby.
- **Online-ready design** (online itself comes later): see [decision 007](decisions/007-local-multiplayer-online-ready.md).
- **Ghost mode:** several cars in one world that pass through each other, so you can drive among agents early.
- Then car-vs-car collision in the `World`: SAT on the polygon hitboxes from step 3d ([decision 004](decisions/004-polygon-hitbox-deferred.md)).
- Then competition: agents learning against each other (multi-agent RL).
- The game leaderboard (slot from step 3a) ranks the cars live.
- **HUD for several cars:** today the panels show only the first car. Add a way to pick which car the panels follow.

### 9. Fuel system

- Limited fuel capacity per car. Driving uses fuel, and an empty tank ends the car's run (through `eliminate`).
- Fuel pickups are triggers with a new effect component (like checkpoints). They spawn from **their own spawn schedule and random stream** (`fuel`), so checkpoint sequences of existing seeds stay the same. Scripted stages can time fuel spawns ([decision 009](decisions/009-stage-format-and-spawn-schedules.md)).
- The observation adds the fuel level and the nearest K fuels, as a new observation version.
- Reward profiles can get fuel terms.

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

- **Experiments to run** (ideas so far): reward profiles, number of rays, network size, algorithm (PPO recommended in [decision 012](decisions/012-agent-training-modes.md), DQN as a comparison), imitation vs RL vs imitation-then-RL, generalization to unseen maps, spotting reward loopholes (like circling forever for distance points), and **compass vs sensor-only agents** (rays that also detect checkpoints and fuel, with no compass: more realistic, slower to learn).

## Refactor scope (step 2, done)

In scope:
- A small in-house ECS core (entities, components, systems, resources)
- Replacing `StateSingleton`/`FieldSingleton` and global `FLAGS` reads with per-world resources
- Moving the car state into components, and the car logic into steering, movement, and sensor systems
- Moving drawing into a render system, separate from the simulation step

Out of scope: any behavior change. The demo must look and drive the same, as the step 1 tests check. That includes keeping the current `Rect` hitbox.

## Target layout

Layers: [decision 002](decisions/002-sim-render-split.md). ECS structure and component and system mapping: [decision 005](decisions/005-entity-component-system.md).
