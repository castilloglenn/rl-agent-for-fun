# Architecture

An ECS (Entity Component System) simulation core, with layers around it. The reasons are in [decision 002](decisions/002-sim-render-split.md) (layers) and [decision 005](decisions/005-entity-component-system.md) (ECS).

```
app.py                 flags -> ConfigDict -> mode (demo / Main stub)
src/ecs/               World: entities, components, resources, systems
src/sim/               Maze Car rules: components, resources, systems, factories
src/envs/maze_car/     MazeCarEnv wraps a World; MazeCarDemo drives it by keyboard
src/render/            Renderer: pygame window, reads the World, never writes it
src/replay/            Replay files: format, recorder (env hooks), replayer
src/drivers/           Who drives: keyboard, baselines, agents (one interface)
src/agents/            Learned agents: model files, policy network, agents/
src/experiments/       Experiment runs: many headless episodes into runs/
stages/, rules/,       Data files: stages (where), rules (how the game is
rewards/, models/,     played and scored), reward profiles (what agents
trainers/, suites/,    learn), models (an agent's network shape), trainers
datasets/              (how it learns), suites (how it's scored), and
                       datasets (which recordings it imitates)
```

Dependencies point one way: `replay` uses `envs`, `envs` uses `sim` and `render`, `render` reads `sim` components, and `sim` uses `ecs`. `sim` and `ecs` never import `render`, `envs`, or `replay`. The env never imports `replay` either: a recorder plugs in through hooks. `agents` uses `drivers` and `replay` (for its driver record), and only `drivers/registry.py` imports `agents`, lazily, so torch loads only when an agent drives.

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
| `resources.py` | `SimConfig` (step rate, car size, ray length, driving limits), `Rng` (the seed, with one named random stream per use), `Stage`, `Rules`, `Field` (spans the stage from (0, 0)), `Walls` (the stage's walls as boxes, step 7a), `SpawnSchedules`, `SimClock`, `RoundState`, and `EventLog` |
| `systems/` | `pose_history_system`, `steering_system`, `movement_system`, `reward_system` (+1 per 10 px forward), `trigger_system` (car touches trigger: apply effects), `sensor_system`, `clock_system`, then `round_system`. The order is fixed by `SIMULATION_SYSTEMS` |
| `elimination.py` | `eliminate(world, car, reason)`: the single way a car leaves a round (walls now, hazards and weapons later). Marks it `Eliminated`, stops it, logs the event |
| `observation.py` | `observe(world, car)`: the agent's 14 normalized inputs, with a versioned layout (`OBSERVATION_NAMES`, `OBSERVATION_VERSION`) |
| `stage.py` | `Stage` (size, walls, spawns, checkpoint rules), `load_stage(name or path)`, validation, and `to_dict()` for embedding in replays |
| `rules.py` | `Rules` (round length, rounds per game, scoring), `load_rules(name or path)`, validation, `to_dict()`, and `with_round_seconds()` (a renamed round-length override). The `Rules` object is also the world resource the reward and round systems read. See [decision 013](decisions/013-game-rules-files.md) |
| `spawning.py` | `SpawnSchedule`: stage + seed decide every spawn. Slot N's candidates depend only on (seed, spawner, N); `random` or `scripted` mode. Random spots keep the border margin from walls too |
| `factories.py` | `create_game(config, label, seed, stage, rules)` (world + car at the stage's spawn + checkpoint: used by the env and tests), `create_world`, `create_car`, `create_start_car`, `create_checkpoint` |
| `geometry.py` | `car_corners` (the 4 real hitbox corners), `inside`, and `max_move_fraction` (how far a move can go before a corner touches the border) |
| `walls.py` | Walls inside the field ([decision 033](decisions/033-walls-in-the-simulation.md)): `Box`, `wall_contact` (the first contact of a moving hitbox, with its normal), `slide`, `overlaps`, `ray_to_walls`, and `rotation_into_walls` |

**The car's position is its float center** (`Transform.x`, `Transform.y`), and `Hitbox` holds its size. The hitbox is the car's 4 real corners. The field border is the only obstacle so far: cars stop exactly on contact (`movement_system`), turns into it are cancelled (`steering_system`), and it stops rays (`sensor_system`).

Geometry and physics rules: [conventions](conventions.md).

## Env (`src/envs/maze_car/env.py`)

`MazeCarEnv` implements `src/envs/base.py` `Environment`, a **Gymnasium-style API** (without the dependency).

**For agents:**
- `reset(seed)` starts a new game (world + car + checkpoint) and returns `(observation, info)`. With `random_seeds=True` (the demo), each reset picks a fresh seed. Otherwise `game.seed` is used.
- `step(action)` returns `(observation, reward, terminated, truncated, info)`:
  - `terminated`: the car is out (wrecked).
  - `truncated`: the round ran out of time.
  - `reward`: from the env's **reward profile** (`MazeCarEnv(config, reward="default")`: a name in `rewards/`, a path, or a `RewardProfile`). The profile is a weighted sum of per-step terms (points, distance points, checkpoints, checkpoint speed, damage, wrecked, contact, stopped, time up, per step, distance, speed, steering change, closest wall; some take parameters), and never changes the game score. `rewards/default.json` is the game points gained, -100 per new wall contact (`contact`, bumps included; pushing on into the wall is the same contact), -500 per full loss of health (`damage` is the share of health lost that step), and -0.25 per step the car ends stopped (`stopped`: idle, or pinned against a wall). It's 0 once the game is over. See [decision 011](decisions/011-reward-profiles.md).
- `info` has `score`, `points` (game points this step), `checkpoints`, `step`, `health`, and `eliminated` (`"wrecked"` or None).
- `get_state()` returns the observation: 15 float32 values from `observe()` (`src/sim/observation.py`). The names are in `observation_names`, and the version is in `observation_version`. See [game design](game-design.md#observation-what-the-agent-sees).
- An action is 5 bools, in `action_names` order: `(turn_left, turn_right, gas, reverse, brake)`.
- Measured: about 49,000 `step` calls per second on one core, headless (observation and reward included).

**For the real-time demo:**
- `step_world(action)`: one simulation step, no drawing. Does nothing once the game is over. It also scores the step with the reward profile (`last_reward`, `round_reward`, and each term's share summed over the game in `round_terms`, from `RewardProfile.contributions`), so the HUD shows the agent reward, by term, while a human drives.
- `game_step(action)`: `step_world`, plus one drawn frame if `config.show_gui` is on (`step` uses it, so an agent can be watched).
- `render(alpha)`: handles window events (R runs `reset()`) and draws one frame, interpolated by `alpha`. Returns the real seconds since the previous frame.

## Drivers (`src/drivers/`)

Everything that decides a car's actions implements **`Driver`** (`base.py`): `reset(seed)`, `act(observation) -> 5 bools`, `record()` (its driver record for replays), and `label` (for the HUD). The demo, runner, replays, and evaluation treat every driver the same.

| File | Contents |
|---|---|
| `actions.py` | The **12 canonical actions** (steering left/none/right × pedal none/gas/reverse/brake) and `canonical_index()`. Every one of the 32 key combinations behaves exactly like one of them ([decision 012](decisions/012-agent-training-modes.md)) |
| `keyboard.py` | `KeyboardDriver(player)`: you. Its record is `{"type": "human", "player", "device"}` |
| `random_driver.py` | `RandomDriver`: a random canonical action every 4 steps (30/s, like agents), seeded. The floor |
| `heuristic.py` | `CompassDriver`: rules on the observation only (steer to the checkpoint, turn away from close walls, brake within stopping range, slow down near an off-center checkpoint so it doesn't orbit it). The bar agents must beat |
| `episode.py` | `run_episode(env, driver, seed)`: plays one game headless, returns an `EpisodeResult` (score, checkpoints, reward, how it ended) |
| `registry.py` | `make_driver(name)`: `keyboard`, `random`, `heuristic`, or `agent:<id>` (best scored checkpoint, else newest) / `agent:<id>@<checkpoint>` / `@best`. An unknown driver or a missing or incompatible agent raises `DriverError`, which `app.py` prints as a clean message |

Baseline results on 30 unseen seeds (box stage, 60 s rounds):

| Driver | Mean score | Checkpoints per round | Survived |
|---|---|---|---|
| random | 13.7 | 0.0 | 100 % (it barely moves) |
| heuristic | 2,502 | 16.2 | 97 % |

## Agents (`src/agents/`)

A learned agent is a folder, built from a model file ([decision 014](decisions/014-model-and-trainer-files.md)):

```
models/<name>.json          network shape: hidden layers, activation,
                            observation version, action set, action repeat
agents/<id>/                (gitignored: local data)
  model.json                a copy of the model, fixed for the agent's life
  checkpoints/initial.pt    weights (plus the model and observation version)
```

| File | Contents |
|---|---|
| `model.py` | `ModelSpec` (from/to dict, validated) and `load_model_spec(name or path)` |
| `network.py` | `PolicyNetwork(spec, obs_size, actions)`: separate policy and value MLPs (multilayer perceptrons). `forward(obs)` returns (action logits, values) |
| `store.py` | `create_agent(id, spec, seed)`: seeded weights, without touching global torch randomness. `load_agent(id or path, checkpoint)`: the newest checkpoint by default (`prefer_best` or `"best"`: the best scored one). `save_checkpoint` |
| `history.py` | `record(folder, event, ...)` appends to `history.jsonl` and rebuilds `profile.json` (`build_profile`: model, lineage, totals, best scores, milestone). Events come from the store (created, branched), training, and scoring ([decision 018](decisions/018-agent-history-and-profile.md)) |
| `trainer.py` | `TrainerSpec` (unknown or missing keys refused) and `load_trainer_spec(name or path)` |
| `ppo.py` | PPO math: `Rollout`, `advantages()` (GAE, no value across an episode end), `update()` (clipped policy loss, value loss, entropy bonus, gradient clipping), `UpdateStats` |
| `driver.py` | `AgentDriver`: decides every `action_repeat` steps and holds the action in between. Deterministic (highest-scoring action) by default, or seeded sampling. Record `{"type": "agent", "id", "checkpoint"}`, label `<id> (agent)` |

**Safety:** loading is refused when the checkpoint was saved for another model, the model uses another action set, or its observation version isn't the env's. Checkpoints load with `torch.load(weights_only=True)`, so a file can't run code.

- Speed: about 9 µs per decision (small model, one CPU core, inference mode).

## Experiment runs (`src/experiments/`)

`run_experiment(name, driver, config, episodes, first_seed, reward, rules)` (`runner.py`) plays episode *i* with seed `first_seed + i`, headless, into a run folder:

```
runs/<date>_<time>_<name>_seed<N>/     (gitignored: local data)
  config.json    driver record, episodes, seeds, full stage, rules, reward
                 profile, game-defining config, observation version, code
  metrics.csv    one row per episode, flushed as it goes: episode, seed,
                 steps, seconds, score, distance points, checkpoints,
                 agent reward, how it ended
  replays/       each new best episode by game score, gzipped and
                 self-verifying (ep0012_score2456.jsonl.gz)
  summary.json   episodes, mean and best score, checkpoints, survival rate
  notes.md       your observations
```

- Ctrl+C stops cleanly: the metrics so far and a summary marked `interrupted` are kept.
- `runs.py`: `list_runs()` / `format_runs()` for `make runs`, and `best_replay(folder)` for `make run_best`.
- Speed: about 0.17 s per 60 s heuristic episode (5 episodes in 0.85 s), replay recording included.
- The keyboard driver is refused: runs are headless.

### Training runs (`src/experiments/training.py`)

`train_agent(agent, trainer, config, first_seed, reward, rules)` runs one **training phase**: it continues the agent's newest checkpoint for `total_decisions` decisions, with episode *i* on seed `first_seed + i`.

```
runs/<date>_<time>_train-<id>_seed<N>/
  config.json    kind "training", agent (model, start checkpoint and
                 decisions), trainer, stage, rules, reward, game config
  metrics.csv    one row per training episode (same columns as runs)
  learning.csv   one row per update: decisions, episodes, mean score and
                 reward of the last 20 episodes, losses, entropy, KL, clip
  replays/       each new best training episode
  resume.pt      everything to continue exactly (after every update)
  summary.json   decisions, updates, last 100 episodes, checkpoints written
agents/<id>/checkpoints/d0100k.pt, d0200k.pt, ...
```

- Each decision samples the policy, holds it `action_repeat` steps, and its reward is the reward profile summed over them. A wreck or time up ends the value chain. That's right for time up too, because `time_left` is in the observation.
- Checkpoints are named by the agent's total decisions at the mark they passed (`d0100k` holds the weights after the first update past 100,000; the exact count is inside). A second phase continues the count.
- **Exact resume** (5a3, [decision 015](decisions/015-exact-resume-by-resimulation.md)): after every update, `runs/<run>/resume.pt` holds the weights, optimizer, torch random state, counters, episode results, and the current episode's seed and decisions. `resume_training(run)` rebuilds the game by re-simulating that episode, and the run ends exactly as if it had never stopped. `last_stopped_run()` finds the newest stopped one.
- Ctrl+C rolls back to the last update (it can land mid-rollout or mid-update), trims the CSVs to it, and saves its weights as a checkpoint.
- Checkpoints record the run that wrote them. Resume is refused if another run trained the agent since, or while `training.lock` names a live process.
- **Branch:** `branch_agent(new_id, source, checkpoint)` (`store.py`) copies the model and a checkpoint into a new agent's `initial`, with `branched_from` and the decision count.
- Reproducible: the same agent, trainer, seeds, and files give the same `learning.csv` and weights. `app.py` sets torch to one thread.
- Training replays record `{"type": "agent", "id", "training": {"run", "decisions"}}` as their driver.

### Evaluation suite (`src/experiments/evaluation.py`)

`load_suite(name)` reads `suites/<name>.json` (a versioned list of scenarios). `evaluate(driver, suite)` plays every scenario deterministically and returns the metrics: `round` (full rounds on fixed seeds: mean and worst score, checkpoints per minute, survival share, wreck rate, contacts) and `braking` (`place_at_wall` puts the car at speed, aimed at a wall, from the seed; the share with no damage). `evaluate_checkpoint` saves one row per checkpoint in `agents/<id>/evaluations/<suite>-v<version>.csv` and the best in `evaluations/best.json`. `evaluate_agent` scores the checkpoints not yet scored. See [decision 017](decisions/017-evaluation-suite.md).

- Training scores each saved checkpoint when the trainer's `evaluate` is on, with a separate env and driver, so training itself is unchanged.
- `load_agent(..., prefer_best=True)` (watching) loads the best scored checkpoint, else the newest. `"best"` asks for it explicitly.

### Imitation (`src/experiments/datasets.py`, `imitation.py`)

`build_dataset(spec, action_repeat)` re-simulates a player's recordings (`datasets/<name>.json`: player, all or kept, min score) into samples: the observation at each decision step, labeled with the most-pressed action over that decision's steps. The idle wait before the first key is left out, and recordings that don't verify are skipped with the reason. `imitate(agent, trainer, dataset, config)` trains the policy on them (cross-entropy), and the value head on the discounted rewards, holding out whole rounds for checking. It saves `clone-e<epochs>`, records an `imitation` phase, and scores the clone. See [decision 019](decisions/019-imitation-agents.md).

### Showcase (`src/experiments/showcase.py`)

`plan(agent)` picks the checkpoints to show (highlights, or all), scoring any unscored ones, and collects each one's suite scores, training time, and badges. `Showcase(folder, stops, config).run()` plays each checkpoint live on the suite's first round seed (deterministic, so it's the evaluation's round) behind a title card, with the replay viewer's `PlaybackControl` plus Left/Right to switch checkpoints. See [decision 020](decisions/020-showcase-mode.md).

### Agent digests (`src/experiments/agents.py`)

`list_agents()` and `format_agents()` for `make agents`, and `agent_summary(id)` for `make agent`: the profile, the score trend over scored checkpoints (a sparkline), and the heuristic's score from the baseline cache. Scoring a checkpoint (`evaluation.py`) records `scored`, `new_best`, and, once, the `milestone`.

## Control center (`src/control/`)

`make control` opens it ([decision 022](decisions/022-control-center-in-pygame.md)). It never runs a command itself: every command is its own process.

| File | Contents |
|---|---|
| `actions.py` | `ACTIONS`: every command, consolidated into 29 actions grouped by the natural steps, each with fields (dropdowns or typed) and the `app.py` arguments it builds. `MAKE_TARGETS` maps each make target to the action covering it |
| `makefile.py` | `read_commands()`: every make target, read from the Makefile, so a test can check that the actions cover them all |
| `choices.py` | `options(command, param)`: dropdown choices from the files on disk (agents, drivers, rules, rewards, stages, runs, recordings, test files), or None for typed values |
| `jobs.py` | `JobManager`: starts each command as a process (plain-text output captured live), and stops (SIGINT, like Ctrl+C), pauses (SIGSTOP), and resumes (SIGCONT) it. A job remembers the run folder it writes, from its `Run: <folder>` line |
| `runs.py` | The Runs tab's data ([decision 023](decisions/023-runs-tab.md)): `scan()` lists every run folder with its status (from our jobs, `training.lock`, the summary, and file times) and progress; `RunData` holds one run's details and chart series, and `CsvTail` reads only the lines a CSV file gained since the last read |
| `charts.py` | `draw_chart()`: hand-drawn line charts (lines, dots, rings, dashed levels) with round ticks and a hover readout. It returns a `Plot` (where it drew), and a full legend drops its highest-`priority` items first |
| `runs_tab.py` | `RunsTab`: the run list, the selected run's header, two charts (the second picked from a dropdown), and its buttons. It can follow a chain, selecting each run the chain starts. A click on a suite dot opens its checkpoint box (watch it drive, branch from it), and a second run of the same kind can be compared ([decision 026](decisions/026-checkpoint-box-and-compare.md)) |
| `training_plan.py` | `make_plan(values, ...)`: the Training tab's form turned into steps (each a Commands tab action), an estimate from past runs, warnings, and what blocks starting ([decision 025](decisions/025-training-tab-and-chains.md)) |
| `chains.py` | `Chain`: jobs run one after another, each only if the one before succeeded; a stop or a failure cancels the rest |
| `training_tab.py` | `TrainingTab`: the form (its fields follow the mode) and the plan box with Start |
| `form.py` | `Form`: a scrolling column of labeled fields (dropdowns, typed, or read-only, with dimmed hints) for the tabs |
| `confirm.py` | `Confirm`: the confirmation box (quit, delete a run, empty the trash): dims the window, Cancel (Esc) and a confirm button (Enter), buttons acting on release |
| `trash.py` | `Trash`: deleting moves folders (or files: named files, recordings) into `trash/` (one entry per delete, with `trash.json`), `restore`, `empty`, and `entries` ([decision 027](decisions/027-trash.md)). `agent_plan` says what deleting an agent moves and keeps |
| `agents_data.py` | The Agents tab's data ([decision 028](decisions/028-agents-tab.md)): `load_agents`, `skills` (the radar's six axes, 0 to 1), `history`, `lineage`, `leaderboard`, and `high_scores` |
| `agents_tab.py` | `AgentsTab`: the roster (cards or leaderboard), and the selected agent's profile, radar, skill history, lineage, and buttons |
| `radar.py` | `draw_radar()`: a skill radar with a reference outline |
| `files.py` | The Files tab's logic ([decision 029](decisions/029-file-editors.md)): `KINDS` (folder, defaults, validator), `items` and `rebuild` (a file as fields by path, and back), `check`, `dump` (the repo's layout), `save` (a changed suite gets the next version), `duplicate` |
| `help.py` | The help texts ([decision 030](decisions/030-units-and-tooltips.md)): every file field by path with its unit, reward terms, form fields, and topics (charts, statuses, skills, columns, badges, vital signs) |
| `tooltips.py` | `Tooltips`: tabs register help areas while drawing (and draw the "i" marker); the window draws the one under the mouse after 0.5 s |
| `recordings_data.py` | The recordings browser's data ([decision 031](decisions/031-recordings-browser.md)): `players`, `recordings` (rows from file names and headers), and `uses` (whether a dataset's rules let a round in) |
| `recordings_view.py` | `RecordingsView`: the table of a player's rounds, with Watch, Keep, Unkeep, and Delete (inside the Files tab) |
| `files_tab.py` | `FilesTab`: the file list per kind, the editor (a `Form` of the file's fields), and Save, Revert, Duplicate as…, and Delete |
| `text.py` | `fit`, `wrap`, and `header`: text helpers the tabs share |
| `stats.py` | `SystemStats.sample(pids)`: CPU, memory, battery, and disk (with `psutil`), plus our jobs' share, and a level (normal, caution, danger) for each |
| `vitals.py` | `VitalsLog`: those readings as a row every 10 s (and on a level change) in `logs/vitals.csv`, with job and window events as notes, rotated at 100 KB ([decision 024](decisions/024-vitals-log.md)); `tail()` for `make vitals` |
| `window.py` | `ControlCenter`: a pygame + `pygame_gui` window, themed like the game window: tabs on top and the machine's vital signs along the bottom, the Commands tab (actions with their fields, scrolling when they don't fit, and the command they run, jobs, and a big console), the Training, Runs, Agents, and Files tabs, and a QUIT? box with Cancel (Esc) and Confirm (Enter) |

## Map editor (`src/editor/`)

`make edit_map STAGE=name` ([decision 035](decisions/035-map-editor.md)).

| File | Contents |
|---|---|
| `model.py` | `EditorModel`: the stage being edited and every edit (walls, the spawn, checkpoints), snapping to a 10 px grid, picking what's under the mouse, undo and redo (a snapshot per gesture), `problem()` (the game's `Stage.from_dict`), and `save()`. `dump_stage`: the stage file's layout |
| `window.py` | `EditorWindow`: a game window mode with the game's layout and camera: tools, selection, and stage cards, help, the field with its grid, and the mouse and keys turned into edits |

## Replays (`src/replay/`)

Details: [decision 003](decisions/003-replay-over-multi-window.md).

| File | Contents |
|---|---|
| `format.py` | `Replay` (header, action changes, end), `write_replay` / `read_replay` (`.jsonl`, or `.jsonl.gz` gzipped), and `to_current_actions` (reads actions by name) |
| `recorder.py` | `ReplayRecorder(drivers)`: plug into `MazeCarEnv(..., recorder=...)`. The env calls `on_reset` (header), `on_step` (stores only action changes), and `on_finish` (end line). Driver records: `human_driver(player)`, `agent_driver(id, checkpoint)` |
| `recordings.py` | Your demo rounds, per player: `RecordingLibrary` (`recordings/<player>/`, the latest 50, and `kept/`, never removed), and `LibraryRecorder`, which saves every round when it ends, and as "stopped" when it's restarted or quit (rounds under 1 s aren't saved). `keep_last()` is K in the demo. `keep_file` and `unkeep_file` move a recording into or out of `kept/` by its path (unkeeping doesn't prune) |
| `viewer.py` | `ReplayViewer`: replay mode in a window (`app.py -replay <file>`). Verifies the replay headless first, then plays it with `PlaybackControl` (SPACE pause, 1-4 for 0.5×/1×/2×/4×, N one step while paused, R restart). Shows its state through a `ModeInfo` |
| `replayer.py` | `Replayer(replay)`: rebuilds the game from the file alone (embedded stage, seed, game-defining config via `config_with_game`, reward profile), re-simulates, and `verify()`s the end line (step, reason, score, reward). Code and observation version differences are reported as notes |

- **Window modes:** `Renderer.draw(..., mode=ModeInfo(...))` shows a mode's label in the left panel's DRIVER section (for example "REPLAY 2× · verified"), its shortcuts in the `?` box, and its messages in the field. The renderer prints each new game event once, with its round time (the control center's console, or the terminal, shows them; headless runs print nothing). `Renderer.poll_events(game_over)` handles Esc (close a box, ask before quitting, or quit when the game is over), Enter, and `?`; `modal_open` tells modes to freeze while a box is open. The renderer doesn't know what the mode is. `Renderer.keys_pressed` lists this frame's key presses for modes with their own controls.
- Recorders get an `on_before_reset` hook, so a round cut short by a restart is finished and saved before the new game replaces it.
- `env.finish_recording()` ends a recording early (for example when the player quits). The replay then verifies up to that step.
- Actions are coerced to plain bools, so agents may pass numpy booleans.
- A full 60 s round is a few KB (about 1.4 KB, or 0.7 KB gzipped, for a short sample round).

## Versions

`code_version()` (`src/utils/version.py`) returns the git commit, plus `-dirty` with uncommitted changes (`unknown` without git). Replays and runs record it, so an out-of-date replay shows when the simulation changed.

## Controllers

A controller decides the car's `ActionInput` before each step. Live, that's a **driver** (above): the demo runs any driver (`--driver keyboard|random|heuristic`), pumping events once per frame and asking the driver once per simulation step. Replays feed recorded actions instead (`Replayer`).

## Rendering (`src/render/`)

| File | Contents |
|---|---|
| `renderer.py` | `Renderer`: owns the pygame window and clock, draws the field view through its camera, and calls the panels |
| `camera.py` | `Camera` ([decision 034](decisions/034-camera.md)): stage to screen and back (`to_screen`, `to_world`). The field view is the box's size; a bigger stage is followed at 1:1 (the default) or fitted (F), and gets a MAP card at the top right (`map_size`; the renderer draws it, the layout's `map_box`), the view growing as tall. `start_intro`, `update`, `hurry_intro`: the map intro at a round's start, blending the fit and follow mappings (`modal_open` holds the game meanwhile). The renderer's `offscreen_marker` places the edge markers |
| `layout.py` | `Layout.for_field`: screen rects for the left panel, top bar, field view, right panel, the optional playback bar under the field, and a map card at the top right for a big stage ([decision 021](decisions/021-window-layout-on-four-sides.md)). The window size follows from the field view's size (the box's, on every stage) |
| `panels.py` | Top bar, one row (HEALTH gauge on the left; round, time, score, status on the right). Left game boxes (driver and mode; game: stage, rules, spawns, seed; score; leaderboard; agent: reward profile, gains, costs, net, the biggest cost, and the sim step and rate, [decision 032](decisions/032-reward-by-term.md)). Right car boxes (car and inputs, sensors, objective, display: FPS, vsync). Every section is its own box, with even 16 px gaps. Text is shortened with "…" to fit. `?` toggles a shortcuts box over the field (each mode's `ModeInfo.shortcuts`). **Retro style: lines and text only**, with colors and bold for distinction. Graphics belong inside the field |
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

Maze walls, multiple cars, and the control center. See [roadmap](roadmap.md).
