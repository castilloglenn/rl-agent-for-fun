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
| **4** | **Stages, replays, and experiment runs** | Done |
| 4a | **Groundwork (urgent, before any file format):** split config into game-defining vs presentation keys, separate the agent reward from the game score, code version stamp ([decision 010](decisions/010-decouple-before-file-formats.md)) | Done |
| 4b | Stage format: the box stage as a file (origin 0,0), loader, spawn schedules (random from seed, or scripted). The stage takes over the game-defining field and checkpoint keys ([decision 009](decisions/009-stage-format-and-spawn-schedules.md)) | Done |
| 4c | **Reward profiles:** agent rewards as weighted terms in `rewards/<name>.json`, separate from the game score ([decision 011](decisions/011-reward-profiles.md)) | Done |
| 4d | Replay format, recorder, and self-verifying replayer (simulation only). Per-slot actions, named actions, driver record (with player), reward profile, code version | Done |
| 4e | Replay mode in the window: pause, 0.5×/1×/2×/4× speed, frame stepping, restart | Done |
| 4f | Baseline drivers: random and heuristic ("compass driver"), and the one driver interface every driver uses | Done |
| 4g | **Game rules** as files: round length, rounds per game, and scoring together in `rules/<name>.json` ([decision 013](decisions/013-game-rules-files.md)) | Done |
| 4h | Experiment runner: headless episodes, run folder, metrics, best-episode replays. The run config records the stage, rules, reward profile, game-defining config, and code version | Done |
| 4i | Record your own demo rounds: per player, latest 50 kept, K keeps a run for good | Done |
| **5** | **Agents** ([decision 012](decisions/012-agent-training-modes.md)) | Done |
| 5a | RL agent and training: torch model, training loop, full checkpoints, pause / resume / branch, evaluation suite (box-map skills). **Milestone: the first skilled agent** | Done (milestone reached 2026-09-27: `rookie`, best d1700k, mean 5,347 vs heuristic 2,574, no wrecks) |
| 5a1 | Agent core: model files (`models/`), policy network, `AgentDriver` (12 canonical actions, action repeat 4), saving and loading agents ([decision 014](decisions/014-model-and-trainer-files.md)) | Done |
| 5a2 | PPO training loop, with trainer files (`trainers/`), as a run folder with learning metrics | Done |
| 5a3 | Full checkpoints (optimizer and random states too), exact resume (`make resume`, `make resume_last`), branch into a new agent ([decision 015](decisions/015-exact-resume-by-resimulation.md)) | Done |
| 5a4 | Car health: wall hits cost health by impact speed (speed into the wall), the car stops on contact, wrecked at 0. Collisions in the rules file, health in the observation, `damage` reward term, HEALTH gauge and hit blink ([decision 016](decisions/016-car-health-and-wall-hits.md)) | Done |
| 5a5 | Evaluation suite: fixed scenarios for survival, checkpoint hunting, braking; scored at each checkpoint, best checkpoint picked (`make eval`, [decision 017](decisions/017-evaluation-suite.md)) | Done |
| 5a6 | Agent storage and history (`agents/<id>/`: profile, history, milestone checkpoints), `make agent` digest ([decision 018](decisions/018-agent-history-and-profile.md)). **Milestone: the first skilled agent**, checked at each scoring | Done |
| 5b | Imitation agents: learn from your recorded runs (behavioral cloning), then optionally keep improving with RL (`make imitate`, [decision 019](decisions/019-imitation-agents.md)) | Done |
| 5c | Showcase mode: watch an agent's progression checkpoint by checkpoint, on the same round, with title cards (decisions, training time, suite scores, BEST / MILESTONE badges) and replay controls (`make showcase`, [decision 020](decisions/020-showcase-mode.md)) | Done |
| 5d | Window layout of modular boxes: a one-row top bar, the game on the left (driver and mode, game, score, leaderboard, agent), the car on the right (instruments, sensors, objective, display), `?` for a shortcuts box, a quit prompt on Esc, P to pause, and your round starting with your first driving key ([decision 021](decisions/021-window-layout-on-four-sides.md)) | Done |
| 6 | Control center GUI: its own window (training setup, runs panel, learning curves, terminal-style console, recordings and datasets, agent roster grid, agent profile pages, agent leaderboard), pause training in place (it stays in memory while you watch replays or live play), plus separate simulation windows for live play and replays | Done, 6e planned ([decision 022](decisions/022-control-center-in-pygame.md)) |
| 6a | Shell and commands: `make control`, every command consolidated into 19 actions grouped by the natural steps, with fields (dropdowns from the files on disk), background jobs (stop = Ctrl+C, pause, resume), live console | Done |
| 6b1 | Runs tab: every run (training, imitation, episodes) with its status read from the files, progress and time left, live learning curves with hover readouts, and stop / pause / resume / resume training / watch best replay ([decision 023](decisions/023-runs-tab.md)). Plus a size-capped vitals log for crash investigation (`make vitals`, [decision 024](decisions/024-vitals-log.md)) | Done |
| 6b2 | Training tab: one form for RL, imitation, or imitation then RL, for an existing agent or a new one (fresh or branched), with the plan in plain words, the terminal equivalent, an estimate from your past runs, and what blocks starting. It runs as a chain of the Commands tab's actions, and the Runs tab follows it ([decision 025](decisions/025-training-tab-and-chains.md)) | Done |
| 6b3 | Branch and compare: click a checkpoint's suite dot to watch it drive or branch a new agent from it, and compare with another run of the same kind (muted lines on both charts) ([decision 026](decisions/026-checkpoint-box-and-compare.md)). Plus deleting a run into a trash, with restore and emptying (`make delete_run RUN=folder`, `make trash`, `make restore TRASH=entry`, `make empty_trash`, a Runs tab button, and a Files group in the Commands tab), each asking first ([decision 027](decisions/027-trash.md)) | Done |
| 6c | Agents tab: the roster as cards (score against the heuristic, mini radar, badges) or a leaderboard by suite score (baselines as reference rows) with high scores, and the profile page (skill radar, skill history, lineage, and buttons to watch, showcase, evaluate, train more, branch, open a run). Plus deleting an agent with its runs into the trash (`make delete_agent AGENT=id`) ([decision 028](decisions/028-agents-tab.md)) | Done |
| 6d1 | Files tab, editors: reward profiles, rules, trainers, models, datasets, and suites as fields by path, checked as you type by the commands' own validators, saved in the repo's layout; duplicate, delete into the trash, and a new suite version on each change ([decision 029](decisions/029-file-editors.md)) | Done |
| 6d2 | Files tab, recordings browser: every recorded round per player (date, seed, score, how it ended, kept, used by dataset mine), with watch, keep or unkeep, and delete into the trash (`make keep`, `make unkeep`, `make delete_recording`, [decision 031](decisions/031-recordings-browser.md)) | Done |
| 6e | Reward by term over training: each episode's per-term reward sums (the game window's AGENT card shows gains, costs, and the biggest cost, [decision 032](decisions/032-reward-by-term.md)) become `metrics.csv` columns, and the Runs tab charts them, so you see when an agent learns to avoid walls (its contact cost shrinking) or finds a loophole ([decision 056](decisions/056-reward-by-term.md)) | Done |
| 7 | Maps: inner walls (rectangles) in stage files, camera for big stages, map editor (walls, spawns, scripted checkpoint sequences). Evaluation suite gains map-based skills (corridors, unseen maps). A reward term for progress toward the checkpoint, so backing out of a dead end pays off without rewarding reversing itself (paying for reversing would let an agent farm reward by rocking in place) | Done |
| 7a | Walls in the simulation: rectangle walls in stage files with the border's physics (stop, slide, damage by impact speed, scraping), rays that see them, checkpoints clear of them, drawn in the field, and the `pillars` and `s_curve` stages ([decision 033](decisions/033-walls-in-the-simulation.md)) | Done |
| 7b | Camera for stages bigger than the field view (which stays the box's size): follow (1:1, centered on the car, the default) or fit (an overview, F switches), with a MAP card at the top right, a map intro (the whole map for 3 s, then a zoom into the car; the game waits, a key cuts the 3 s short), and edge markers pointing to a checkpoint outside the view; the `arena` stage (1200 × 1200) ([decision 034](decisions/034-camera.md)) | Done |
| 7c1 | Map editor: `make edit_map STAGE=name` (and "Edit a map" in the control center), tools to draw, move, resize, and delete walls, place and turn the spawn, and add checkpoints in order or random; a 10 px grid, undo and redo, the game's own validation as you edit, and save ([decision 035](decisions/035-map-editor.md)) | Done |
| 7c2 | Map editor: test drive the map being edited in the same window and come back (T; Shift+T watches the heuristic), never recorded, and resize the stage by dragging its edges ([decision 035](decisions/035-map-editor.md)) | Done |
| 7c3 | Maps tab in the control center: a card per stage (a drawn preview, size, walls, checkpoint mode), which agents trained on it and whether a suite uses it, and buttons to edit, drive, watch an agent on it, duplicate, and delete into the trash (the box and any stage a suite uses are protected) ([decision 036](decisions/036-maps-tab.md)) | Done |
| 7c4 | Health on the car: a thin bar (3 px, about a car length wide) above the car instead of the top bar's HEALTH gauge, level on screen (it doesn't turn with the car) and a fixed gap above the car's farthest corner at any heading, green when full, amber, then red as health drops (the gauge's colors). Every car gets its own (multiplayer, step 10), and fuel joins as a second bar under it (step 9) | Done |
| 7c5 | Settings of yours: `user/settings.json` (out of git), display only, so the simulation, replays, and scores never change: the car's bars above or below it, and always or only when damaged; the lines (rays, hitbox, and the checkpoint guide together, the same switch as H); the trail on when watching or replaying (T); big stages starting in follow or fit (F); the keys change the settings too, so both always agree; the map intro; the FPS cap. In the game window, O opens a SETTINGS box (arrows pick and change, applied live and saved as you go, Esc closes); listed in the ? shortcuts. Plus the control center's tabs in the order you'd use them (Training first, Commands near the end) ([decision 040](decisions/040-settings-of-yours.md)) | Done |
| 7e | Progress toward the checkpoint along a drivable path around the walls (`src/sim/paths.py`), a new reward term the agent never sees, and the default reward rebuilt on it: +0.1 per px closer (half while reversing, full cost farther), +500 per checkpoint, -100 per wall contact, -1000 per full loss of health, -3000 for a wreck, -0.25 per step stopped; game points no longer count ([decision 041](decisions/041-progress-reward.md)). Moved up, before 7c6. Amended after agent-1 drove backward nearly all the time: progress while reversing pays nothing (`"reverse": 0.0`) | Done |
| 7c6 | Settings tab in the control center: the same settings as dropdowns by group, saved on each pick, and a change made in a game window shows up here too; new game windows pick them up ([decision 040](decisions/040-settings-of-yours.md)) | Done |
| 7d1a | Built-in and your files, storage: one lookup for every named file (`src/utils/named_files.py`: built-in first, then `user/<kind>/`), used by every loader, dropdown, the Files tab, the Maps tab, the map editor, and the trash; a new file goes to `user/`, never under a built-in's name; `user/` is out of git, and your `ruins` map moved there ([decision 039](decisions/039-skills-suite-and-built-in-files.md)) | Done |
| 7d1b | Built-in and your files, screens: built-ins read-only in the Files tab (a BUILT-IN badge, Duplicate instead of Save and Delete), the map editor (Save as a new name), and the Maps tab (Delete off); the trash takes only your files; dropdowns list built-ins first and tag yours ([decision 039](decisions/039-skills-suite-and-built-in-files.md)) | Done |
| 7d2 | A fixed distance scale for the agent: rays and the checkpoint distance divided by 980.5 px (the box's diagonal, `DISTANCE_SCALE` in `observation.py`) on every map, clipped at 1. Identical on box-sized maps, so box agents and the behavior tests don't change; agents trained on bigger maps (the arena) learned the old scale ([decision 042](decisions/042-fixed-distance-scale.md)) | Done |
| 7d3 | Skills suite, in two parts (7d3a, 7d3b): 7 skills in 3 groups (Handling: Braking, Threading; Hunting: Open field, Long range; Walls: Obstacles, Corridor, Detour) on the box and 5 new built-in `skill_` maps, 5 episodes each, scored per skill at every checkpoint (about 8 s per checkpoint), replacing box-v1 for new scores (its history stays). Training on a test map warns ([decision 039](decisions/039-skills-suite-and-built-in-files.md)) | Done |
| 7d3a | The 5 built-in test maps: `skill_gaps` (3 wall columns, one 40 px gap each, checkpoints in order through them), `skill_long` (1600 × 1200, empty, random checkpoints at least 500 px from the car), `skill_pillars` (12 scattered pillars, random checkpoints), `skill_corridor` (a serpentine lane, checkpoints in order along it), `skill_detour` (a U open away from the start, its checkpoint inside). Each checked by the game's own stage check and for a drivable path to every checkpoint | Done |
| 7d3b | The skills suite's scoring: `suites/skills.json` (format 2) replaces `box`, a score per skill at every checkpoint, each as a share of the heuristic's (counted as at least 100), the best checkpoint by the average share, the milestone at an average above 1.0 with under half the rounds wrecked, and a warning when training on a test map ([decision 043](decisions/043-skills-suite.md)) | Done |
| 7c7 | Data in sync across the control center: one watcher checks every data folder (agents/, runs/, recordings/, trash/, the named files and their `user/` twins) every 0.5 s by modification time, so anything added, removed, or renamed, by a tab, a job, a terminal, or a game window, reaches every tab within half a second. Each tab rebuilds only what the change touches (dropdowns and lists), keeps your picks that still exist (a deleted one falls back to its default, with a message), never rebuilds an open dropdown under the cursor, and opening a tab always reads fresh. Edits inside a file (an agent's scores) stay on each tab's own 1 to 2 s timer. It fixes, for example, a deleted agent staying in the Training tab's Agent dropdown ([decision 044](decisions/044-data-in-sync.md)) | Done |
| 7c8 | Showcase fixes: the window opens at once with a getting-ready card that shows each step (scoring the unscored checkpoints, about 5 s each; the heuristic's scores for this code, about 9 s once), scoring in the background so the window never freezes, Esc cancels. The baselines' cache keyed to a fingerprint of only the files that can change their scores (the simulation, the env, the baseline drivers, the suite with its maps and rules), not the whole commit, so a commit to the control center or the docs no longer recomputes them. And any skill's map: M cycles the suite's 7 skills in the showcase, each on its own first seed and round length (the round the evaluation scored), the title card showing that checkpoint's share on it; the control center's Showcase action gets a Skill field (Open field by default). Found 2026-09-30: agent-1's showcase took about 30 s with no window (2 unscored checkpoints, a stale baseline cache after a commit) ([decision 045](decisions/045-showcase-fixes.md)) | Done |
| 7c9 | Driving style: how an agent spends its decisions, counted while its checkpoints are scored (no extra games): the share of forward, braking, coasting, and reversing, and of turning left, right, or straight, per checkpoint, so its style shows next to its skills. The Agents tab profile shows its best checkpoint's style as a bar, with a warning when one habit dominates (for example reversing most of the time; the good mix is mostly forward, with braking, turning, and some reversing), and the Runs tab can chart it over training. Asked for 2026-09-30 after seeing an agent reverse all the time ([decision 046](decisions/046-driving-style.md)) | Done |
| 7c10 | Agent nicknames: a display name of yours for an agent ("Reverse Guy"), saved in its profile and changeable anytime, even while it trains, from a Nickname field in the Agents tab profile; shown wherever the agent's name shows (cards, leaderboard, digest, showcase, dropdowns as "Reverse Guy · agent-1"). Its id stays the same, so commands, runs, lineage, and history keep working; no `make` target (targets take one parameter) ([decision 047](decisions/047-agent-nicknames.md)) | Done |
| 7c11 | The Agents tab's details, redesigned to fit what's coming: a fixed header (the name on up to two lines, never cut short; the id, model, and training on the line under it; the nickname field), then sections: Overview (milestone, key numbers, a driving bar with its warning), Skills (the radar and the history chart, full height; 7d4's chart lands here), Driving (the pedals as stacked bars next to the heuristic's, the turning split, a moving-backward gauge with its warning line, and the pedals over training), and Lineage. Cards fit a two-line name with the id under it; a leaderboard cell cut short shows whole on hover ([decision 048](decisions/048-agent-details-sections.md)) | Done |
| 7c12 | Tab shortcuts in the control center: Cmd+1 to Cmd+7 on a Mac (Ctrl+1 to Ctrl+7 on Windows) open the tabs in their order (Training, Runs, Agents, Maps, Files, Commands, Settings), shown in each tab's tooltip | Done |
| 7c13 | Pick the map in the game window: M opens a MAPS box (a list, and a preview of the highlighted map with its size, walls, and checkpoints) wherever a driver drives (Watch it drive, Watch an agent or the heuristic: every stage) and in the showcase (the suite's skills with their maps, replacing M's cycling); a pick starts a fresh round there. Not while you drive or test drive. The stage preview moved to `src/render/` ([decision 052](decisions/052-map-picker.md)) | Done |
| 7c14 | Where a replay comes from: a SOURCE card in the replay window (training run, episode, decisions then, mix; or your recording), a best replay per map for mixed runs (M picks one when watching the run's best), and a spinner while the showcase gets ready ([decision 053](decisions/053-replay-source-and-best-per-map.md)) | Done |
| 7c15 | Imitate the heuristic, then RL: record any driver's rounds headless as recordings (`make record_heuristic STAGE=basics`, a stage or a mix, the Commands tab's "Record a driver's rounds"), a built-in `heuristic` dataset, and `make imitate_heuristic AGENT=id`; the Training tab's "Imitation, then reinforcement learning" with it does both ([decision 054](decisions/054-imitate-the-heuristic.md)) | Done |
| 7c16 | Runs that are still starting: a "starting" row at the top of the Runs list for each job or plan that hasn't written its run folder yet (an imitation builds its dataset first: 52 s), selected at once when a plan starts, with a spinner, what it's doing (imitation now says "Building the dataset: round 21 of 50"), the time so far, and the plan's next steps; it turns into the run when its folder appears ([decision 055](decisions/055-starting-runs.md)) | Done |
| 7c17 | The Maps tab: All, Built-in, and Mine buttons above the cards filter them (the count follows; picking a hidden map, a new one for example, shows all), and the cards sort newest first by default | Done |
| 7d4 | Skills chart and radar: the Runs tab's second chart's first option (the score chart stays on top), with one line per skill, each as a share of the heuristic's score on it (1.0 = the heuristic), marked "trained here" for a map it trained on (the best checkpoint by average share moved into 7d3b); the Score chart keeps the training line, and a dot's box shows its score and share; the Agents tab radar shows the 7 skills, its rim at 1.5 times the heuristic; the skill history offers each skill's share; a full chart legend wraps onto rows under the header ([decision 049](decisions/049-skills-chart-and-radar.md)) | Done |
| 7d5 | Mixed-map training, in two parts (7d5a, 7d5b), against forgetting (rookie-to-arena lost box skill, 5,347 to 3,325, while learning the arena): one phase trains on several maps, so the agent never stops practicing any of them, and a built-in training mix covers every skill without the `skill_` test maps. After 7d4, so the Skills chart shows whether it works | Done |
| 7d5a | Map mixes: a named file `mixes/<name>.json` (built-in, or yours in `user/mixes/`, edited in the Files tab) lists stages, and a mix goes wherever a stage name goes for training (`-stage <mix>`, the Training tab's Stage dropdown as "mix: <name>"). Episode i plays map i mod n, in turn, seeds unchanged, resume exact. The run config records the mix and its maps, `metrics.csv` gets a `stage` column, the Runs header says "mix <name> (n maps)", the training line is "training (mixed)", the Skills chart marks every skill whose map is in the mix as trained here, the test-map warning covers every map in it, and watching a mixed run plays its first map. Plus scripted courses that start anywhere: a stage's scripted checkpoints can start at a checkpoint picked from the seed (`"start": "seeded"`; the default stays the first, so the `skill_` maps don't change), so a weak agent still practices every zone. A built-in `basics` mix (box, pillars, s_curve, arena) ([decision 050](decisions/050-map-mixes.md)) | Done |
| 7d5b | Training courses: two built-in maps that each run through several skill zones in order, with scripted checkpoints that loop and start anywhere: `course_small` (gap columns, a U pocket, a winding lane) and `course_large` (a pillar field, a winding lane, a long straight back), and the built-in mix `skill_training`: box (Open field, and Braking in its turns), arena (Long range), and the two courses. The routes and gap heights differ from the `skill_` maps, which stay unseen. Fewer maps than one per skill, and the agent practices going from one skill to the next. A test checks every checkpoint of every scripted stage has a path from the one before ([decision 051](decisions/051-training-courses.md)) | Done |
| 7f | Training fixes after agent_2's collapse (a heuristic clone at share 1.27 fell to 0.27 after 1M decisions, coasting half the time), in five parts | Done |
| 7f1 | The contact cost counts a new wall contact only after 0.5 s clear of walls (the `contact` term's `clear`): wiggling against a wall made one round's contact cost reach -20,000 ([decision 057](decisions/057-contact-after-a-gap.md)) | Done |
| 7f2 | Easy and hard training maps, for a manual curriculum: `course_small_easy` (the same layout as `course_small`, with 80 px gaps, lanes about 150 px wide, and 28 breadcrumb checkpoints, each in a straight line from the one before with room for the car, test-checked; the heuristic drives 24 of them in 60 s, where it gets 0 to 1 on hard), and the mix `skill_training_easy` (box, arena, `course_small_easy`, `course_large`); `course_small` stays the hard version. Breadcrumbs alone weren't enough: the heuristic can't drive through a gap under about 110 px head-on (its wall rule), so a clone inherits that and RL must unlearn it on hard. Train easy first, then hard, keeping earlier maps in the mix ([decision 058](decisions/058-easy-training-course.md)) | Done |
| 7f3 | 12 rays, denser in front (0, ±15, ±30, ±45, ±90, ±135, 180 degrees): a 48 px gap shows from 184 px and a 30 px pillar from 115 px (with 8 rays 45° apart: 63 and 39 px, closer than braking from full speed takes); the observation grows from 15 to 19 numbers (version 1 kept: no agents existed); the heuristic and its scores don't change. And the side panel as instruments: a speed bar, steering slider, heading dial, a sensor radar with the stopping distance, a checkpoint arrow, and steady numbers (a mean, redrawn 4 times a second). A path compass or memory stays a separate decision ([decision 059](decisions/059-twelve-rays-and-instruments.md)) | Done |
| 7f4 | Train a new agent from the heuristic clone with the curriculum (7f5: `skill_training_easy`, then `skill_training`), seeing the route sensor and stuck timer (7f7); watch Skills and Reward by term for a drift, and check the curriculum's level changes against the charts. agent_3 (the navigator's clone, `finetune`, 2M decisions): no drift (share 1.7 to 2.0 throughout, where agent_2 slid from 2.13 to about 1.2), average share 1.67, best d0100k at 2.25, level 2 at about 580k; its training score rose while the test maps stayed flat, and Detour (0.86) stays below the heuristic. Kept as the driver to beat, not the final one: fuel (step 9) changes the game | Done |
| 7f5 | Automatic curriculum, built before training (your call): a named file of levels (a mix and a goal each, a minimum stay, a cap), judged on the training maps (the agent's checkpoints a minute over its last 20 episodes on each map, against the heuristic's there, measured once and cached), moving up when every map beats the heuristic and has leveled off, or at the cap; earlier maps keep a quarter of the episodes; the level saved for exact resume, in the history (a new phase picks it up), in `learning.csv`, the Runs header, and as marks on the charts. The built-in `skills`: easy, then hard; `make train_curriculum AGENT=id` ([decision 063](decisions/063-automatic-curriculum.md)) | Done |
| 7f6 | A stopped agent must press gas or reverse: at speed 0 the actions with no pedal or the brake are blocked in the network (moving, all 12 stay), and datasets leave sitting still out; it ends the stuck pattern of steering or braking in place. Built before 7f4's training ([decision 060](decisions/060-a-stopped-agent-moves.md)) | Done |
| 7f7 | A sense of direction and of being stuck (the agent sees 12 wall distances and a straight-line compass, so with a wall between it and the checkpoint it pushes into the wall until time runs out; you see the whole map): **a route sensor**, general for any target: a remembered waypoint along the shortest drivable route (about one corner ahead, from the same route field as the progress reward, computed once per spawn since walls don't move), refreshed when reached or every 2 s, seen as its direction relative to the car (sin, cos, every step) and the remembered route distance; and **a stuck timer** (seconds since the last progress). The observation grows from 19 to 23 numbers; the heuristic doesn't use them and stays the 1.0 bar. The route knows only the map's walls: other cars (step 10) are seen by the rays, so it never needs updating for them. Fuel (step 9) reuses the route sensor per fuel slot. Scoring a checkpoint takes about 17 % longer; training nothing more (the reward's route fields are shared) ([decision 061](decisions/061-route-sense-and-stuck-timer.md)) | Done |
| 7f8 | Seeing what the agent senses and thinks, live and in replays: with the lines (H), its remembered waypoint (a violet diamond, a dashed line, a pulse when refreshed), the rest of its remembered route faint (a setting, on by default); a Stuck row in OBJECTIVE (a ring around the car was tried and removed: the row is enough); and a MIND card when an agent drives: its next move's odds (steering, pedal) and its outlook (the value head) ([decision 062](decisions/062-seeing-what-the-agent-senses.md)) | Done |
| 7f9 | Taking over while watching, for testing only: holding a driving key drives the car, letting go hands it back; the agent keeps deciding (its MIND shows what it would do) and carries on from there; "YOU are driving" and this round's tally in the DRIVER card; nothing recorded or learned ([decision 064](decisions/064-taking-over-while-watching.md)) | Done |
| 7f10 | The game window rearranged: the game on the left (driver, game, score with collected, leaderboard or source, display) and the map (big stages) and the car and its AI on the right: CAR (speed, steering, keys), SENSES (one radar with the rays, the stopping arc, the checkpoint compass and the route waypoint on its rim, the distances, the stuck bar), MIND (a fixed grid of the 12 actions, the pick outlined, smoothed) and REWARD ([decision 066](decisions/066-game-left-ai-right.md)) | Done |
| 7f11 | Following the route pays more: the progress weight from 0.1 to 1.0 per px, after agent_1 (trained up the curriculum) failed the arena and `course_large`, where following the route earned about +100 a round and the walls cost about -500; not a separate heading bonus, which could be farmed ([decision 067](decisions/067-progress-pays-more.md)) | Done |
| 7f12 | A teacher that follows the route: `navigator`, a hand-written driver steering at the route waypoint, judging gaps with the narrow front rays, and backing out when stuck; recorded and cloned (`make record_navigator`, `make imitate_navigator`), never scored (the heuristic stays the 1.0 bar). It beats the heuristic on every map: `course_small` 0.8 → 20.5 checkpoints a minute, `course_large` 6.9 → 21.7. It's recorded on `route_lessons`, where the route bends away from the compass about 42 % of the time: three new maps (`route_rooms`, `route_spiral`, `route_switchbacks`) with s_curve, `course_large`, the arena, and the box ([decision 069](decisions/069-navigator-teacher.md)) | Done |
| 7f13 | A gentler trainer for continuing a clone: `finetune` (a third of the learning rate, a tenth of the entropy bonus), after agent_2 (the navigator's clone, default trainer) peaked at share 2.13 and slid to about 1.2 as its choices grew more random (entropy 0.23 to 0.81); `make finetune AGENT=id` ([decision 070](decisions/070-finetune-trainer.md)) | Done |
| 7f14 | Being stuck costs reward: nothing for 3 s without getting closer along the route than its best, then rising to -0.5 per step at 10 s, after an agent circled near a checkpoint for 29 s with its stuck input reading 29 s (an input only informs; the reward makes using it pay). The navigator pays 0 to -12 a round, the heuristic up to -2,589 on `course_small` ([decision 071](decisions/071-stuck-cost.md)) | Done |
| 7f15 | No turning back for a passed waypoint: it's refreshed the moment the car is closer to the checkpoint along the route than the waypoint is, and its reach widens from 30 to 45 px; before, a car sweeping past it turned back to collect it ([decision 061](decisions/061-route-sense-and-stuck-timer.md)) | Done |
| 7f16 | The route sense, faster: the walk to the waypoint checks only nearby walls (the same waypoints, 3 to 7 times faster), and an env keeps its route fields across games (a course's checkpoints are built once) ([decision 061](decisions/061-route-sense-and-stuck-timer.md)) | Done |
| 7f17 | The Training tab keeps to what worked for the basic controls: the `finetune` trainer (not `default`) up the `skills` curriculum (no single stages or mixes); the Commands tab and make targets keep every choice ([decision 072](decisions/072-training-tab-keeps-what-worked.md)) | Done |
| 7g | Expert labelling (human-gated DAgger: you label only where you take over): watching an agent's newest checkpoint, C turns REC corrections on (`make correct AGENT=id`), and each round you took over in is saved to `recordings/Corrections/` with your stretches marked; the `corrections` dataset keeps only your moments, each counted 10 times, with the heuristic's driving; a short, gentle imitation phase (`correct`: 10 epochs, a third of the learning rate; `make imitate_corrections AGENT=id`), then RL again ([decision 068](decisions/068-expert-labelling.md)) | Done |
| 7g2 | Choosing which rounds an imitation teaches, part A: a "Rounds" row in the Training tab opens a table of the dataset's rounds with tick boxes (when, map with a test tag, the agent watched, your seconds, score), filters (this agent's line, test maps hidden), the clicked round's details, and a footer with what's ticked and warnings; ticked by default: all but rounds on a test map and corrections of other agents; the ticked go to `-imitate --recordings`, recorded in the run's config ([decision 074](decisions/074-choosing-rounds-to-teach.md)) | Done |
| 7g3 | Choosing rounds, part B: the clicked round's preview, its path on a mini map (re-played in the background, a spinner till then) with your stretches in orange, a timeline of your takeovers, and Watch from 2 s before your first takeover (`-replay --replay_step`, the Commands tab's "From step") ([decision 074](decisions/074-choosing-rounds-to-teach.md)) | Done |
| 7h | Guard rails against features breaking each other: every command checks its arguments first (named files exist, its stage is a kind it plays: a curriculum only for training, a mix for training and recording; `app.py -check` checks and stops), and tests that every form default is one of its choices, every action with every choice its dropdowns offer passes the check, and every make target's command does; plus a consumer sweep in each step's report ([decision 065](decisions/065-guard-rails.md)) | Done |
| 8 | Parallel environments for faster training, before the new features (each changes the observation, so every agent trains again): one network drives several games at once in lockstep, about 4 first with memory measured ([decision 038](decisions/038-jobs-share-the-machine.md)); everything that reads rounds keeps working; the Training tab picks how many games, and the Runs tab shows it. No separate watching window: the Runs tab and replays already follow training | Done |
| 8a | Several games at once in training: workers without torch (about 0.05 GB each), the games stepping together with one network pass, the rollout of 2,048 split over them, rounds numbered by start with a `game` column, a mix's map furthest behind and the curriculum counting at the start, best replays saved by the workers, resume with fresh rounds, `--games` (default 4) as the most, the count following memory and CPU, and the guard counting the workers. Measured: 1 game 821 decisions a second, 2 games 1,023, 4 games 984: `course_small`'s route sense sets the pace ([decision 073](decisions/073-parallel-games.md)) | Done |
| 8a2 | A waypoint chosen close is held: one chosen inside the 45 px reach counted as reached the next step and was chosen again, almost every decision on `course_small` (2,811 times a round), the game that set the pace for all; now it's reached within half its distance when chosen. Training: 1 game 1,380 decisions a second, 4 games 2,099 (before step 8: 821). The navigator drives the same ([decision 061](decisions/061-route-sense-and-stuck-timer.md)) | Done |
| 8b | Picking the games in the window: "Games" (1 up to the cores minus 3, default 4) in the Training tab and the Commands tab's Train; the plan says "up to 4 games at once (fewer while the machine is busy)" and estimates from past runs with the same most (else any, said so); the Runs header shows "3 of up to 4 games" ([decision 073](decisions/073-parallel-games.md)) | Done |
| 9 | Fuel system: limited capacity, fuel spawns (its own spawn schedule and random stream), observation adds fuel level and the nearest K fuels by route, each slot with the straight compass and the route sensor (7f7); the agent learns whether fuel or the checkpoint comes first from the reward (checkpoints score, running dry costs). The car's fuel shows as a second thin bar under its health bar (7c4). Then train a driver for it | Planned |
| 10 | Multiple cars and local multiplayer: game setup lobby (stage, rounds, seed, agents, human players), keyboard and gamepad controllers, ghost mode first (no car-vs-car collision), then car-vs-car collision (SAT), then angled (line segment) walls, then competition. Game leaderboard fully used | Planned |
| Later | Time-attack rules (the game score rewards fast checkpoints, for everyone: a rules file option), hazards ([game design](game-design.md#hazards-future)), multiple rounds per game (the rules file already has `rounds`; per-round state, see [decision 010](decisions/010-decouple-before-file-formats.md)), online multiplayer, weapons and skills, grip and drift physics (see [below](#later-grip-and-drift-physics)), a **colosseum mode**: car-vs-car battles (last car standing, health as hit points, damage from rams and weapons) instead of only collecting points, with the event log as its match feed, clicking the mini map to move the view (replays of big stages, [decision 034](decisions/034-camera.md)), a **race to the finish**: scripted checkpoints that end the round after the last one (or after a set number) instead of looping, scored by time, a rules or stage option | Idea |

## Step details

### 3. First game rules in the box map

The rules and values are in [game design](game-design.md#first-goal-roadmap-step-3). Build notes:

- Each sub-step changes behavior on purpose. Regenerate the fixtures (`python -m tests.generate_behavior_fixtures`) and add scenarios for the new behavior, for example tapping vs holding the brake, coasting to a stop, and a crash.
- The round timer and checkpoint randomness are world resources, seeded per round. Timer and randomness stay deterministic ([conventions](conventions.md#determinism-must-keep)). Since 4b, checkpoints follow the stage's spawn schedule.
- New config keys (all values tunable): reward distance, drag, brake strength, `round.seconds`, `game.rounds`. Checkpoint radius and margins started in config and moved to the stage file in 4b; round length, rounds, and scoring moved to rules files in 4g.
- The HUD shows the remaining time, score, and 8 ray distances.
- Observation layout: [game design](game-design.md#observation-what-the-agent-sees). Normalize every input, and keep the layout in one place so the agent and replays agree on it.

### 3a. Simulation window UI

```
┌──────────────────────────────────────────────┬─────────────────────┐
│ ROUND 1/1  TIME 00:42.3  SCORE 1,240 DRIVING │ CAR: speed, stop    │
│ DRIVER STAGE RULES SPAWNS SEED REWARD        │  dist, pedal,       │
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
- **Game leaderboard slot:** ranks cars in the current game by score. Built as a panel section now, and it fills in once there are several cars (step 10) or parallel games (step 8).
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
- SAT (Separating Axis Theorem) is added later, for inner walls (step 7) and car-vs-car collision (step 10), using this polygon.
- `rotated_bounds` was removed, together with the integer-rect movement helpers.
- **Exact contact:** moves go as far as possible until a corner touches the border, instead of stopping up to a step short. Turns into the border were cancelled; since 3f, touching the border is a crash.
- The start position became exactly a quarter of the field's width, mid height, dropping the old truncation quirk. Since 4b, it's the stage's spawn.

### 4. Stages, replays, and experiment runs

Goal: run many episodes headless, save each run's results, keep recordings of the best episodes, and play any recording back. No neural network yet: two baseline drivers exercise the pipeline, and become the benchmark trained agents must beat.

#### 4a. Groundwork (urgent)

Fixes to code that already exists, so the file formats in 4b to 4i start clean. Details: [decision 010](decisions/010-decouple-before-file-formats.md).

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
- Terms are things measurable in one step: points, checkpoints, damage, wrecked, time up, per step, distance moved, speed, steering change, closest wall.
- Unknown terms or a wrong format fail early with a clear error. New terms can be added later without breaking old profiles.
- **The game score is never affected**, so agents trained with different profiles still compete on the same leaderboard.
- The env takes a profile by name or path. Replays (4d) and runs (4h) record the profile used, and agent profiles (step 5) show "trained with".
- **Time bonus** (added after 4c): the `checkpoint_speed` term pays more the faster a checkpoint is reached (and `distance_points` counts driving only, so `time_bonus` doesn't also add the game's flat +100), and terms can take parameters (`{"weight": 100, "window": 10}`). Try it with `make maze_car_reward REWARD=time_bonus`. It only changes the agent reward: a time-attack game mode, where the game score itself rewards speed, is listed under Later.
- Profiles have a `name` and an optional `description`. The window shows the profile name in the top bar, and the agent reward (last step, this game) in the side panel, also while a human drives.

#### 4d. Replay format

Details: [decision 003](decisions/003-replay-over-multi-window.md).

- **Inputs, not positions:** a header (format version, stage **embedded in full**, seed, game-defining config, reward profile, observation version, drivers) plus the actions, re-simulated on playback.
- **Per simulation step**, storing only changes ("from step 1,834: gas + left"). A full 60 s round is a few KB.
- **Self-verifying:** the file stores the final score and step. A mismatch on playback means the simulation changed since recording, and the replay is flagged instead of silently showing wrong driving.
- JSON Lines, readable as text.
- **Per-slot actions:** every action line is keyed by slot (`{"step": 1834, "actions": {"1": [...]}}`), and the header lists the slots and their drivers. Multi-car replays (step 10) then need no format change.
- **Named actions:** the header stores `action_names`, and actions are read by name. Actions added later (weapons, skills) count as "not pressed" in old replays.
- **Driver record:** `{"type": "human", "player": "zen", "device": "keyboard"}` or `{"type": "agent", "id": ..., "checkpoint": ...}`, not just a label. The **player** name groups a person's runs into an imitation dataset (5b).
- **Code version** in the header, so an out-of-date replay shows when the simulation changed.

#### 4e. Replay mode

- `python app.py -replay <file>` opens a simulation window playing the recording.
- Controls: SPACE pause, 1 to 4 for speed 0.5× / 1× / 2× / 4×, N steps one frame while paused, R restart, H lines, Esc quit (`make replay FILE=<path>`). The HUD shows "REPLAY", and the top bar shows the replay's driver, stage, seed, and reward profile as usual.
- The replay is **verified up front** (a quick headless re-simulation): the top bar shows "REPLAY 2× · verified" in green, or "OUT OF DATE" in red. At the end, the field lists the verification result and any mismatches.

#### 4f. Baseline drivers

- **Random:** random actions, the floor.
- **Heuristic ("compass driver"):** hand-written rules: steer toward the checkpoint using the compass inputs, brake when a travel-path ray is short.
- Both use only the env API (observation in, action out), exactly like a trained agent will.
- **One driver interface** for every driver: observation in, action out. Random, heuristic, RL agents (5a), and imitation agents (5b) all plug in the same way, so nothing downstream (runner, replays, evaluation, live play) needs special cases.
- **Built** (`src/drivers/`), with the keyboard as a driver too, so `app.py -demo maze_car --driver heuristic` shows a baseline live. On 30 unseen seeds: random scores 13.7 (no checkpoints), the heuristic 2,502 (16.2 checkpoints per round, 97 % survival). Slowing down near an off-center checkpoint took it from 0.9 to 16 checkpoints per round: at full speed it orbited them.

#### 4g. Game rules

Details: [decision 013](decisions/013-game-rules-files.md).

- **Rules files** in `rules/<name>.json`, starting with `rules/standard.json`: today's exact values (one 60 s round, +1 per 10 px, +100 per checkpoint). They replace `config.round`, `config.game.rounds`, and `config.rewards`.
- Three swappable things, each a named file: **stage** (where), **rules** (how the game is played and scored), and **reward profile** (what an agent learns from).
- Chosen with one setting: `--rules <name>` (and `make maze_car_rules RULES=<name>`). The top bar shows `RULES <name>`.
- Replays embed the full rules, like stages. Runs record them.
- **Leaderboards compare scores only within the same stage + rules**, since a longer round naturally scores more.
- With `standard`, nothing behaves differently: the fixtures only change their config header.

#### 4h. Experiment runner

- `python app.py -run <name> --driver heuristic --rules standard --reward default --stage box --episodes 200`, headless at full speed, with a one-word make target per parameter (for example `make run_driver DRIVER=heuristic`).
- Each run gets its own folder in `runs/`, which is **gitignored** (results are local data):

```
runs/<date>_<name>_seed<N>/
  config.json     all settings: stage, rules, reward profile, driver, seeds, versions
  metrics.csv     one row per episode: seed, steps, score, distance points,
                  checkpoints, agent reward total, how it ended
  replays/        recordings of each new best episode
  checkpoints/    model files, from step 5a (ep1000.pt, best.pt, ...)
  notes.md        your observations
```

- Runs can be listed, compared (learning curves on one chart), replayed, and reproduced with the same seed.
- `config.json` records the **reward profile** used (name and full content), the **game-defining config**, and the **code version**.
- **Built** (`src/experiments/`): folders are `runs/<date>_<time>_<name>_seed<N>/`, with a `summary.json` too. Best replays are chosen by **game score** (the fair measure). Ctrl+C keeps the metrics so far. `make runs` lists runs, and `make run_best RUN=<folder>` watches a run's best episode. `make run` became `make main`, so "run" now means experiment runs.
- Expected sizes, as ESTIMATES: replays a few KB each, model files KB to a few MB.

#### 4i. Record your own demo rounds

- Every round you play in the demo is saved as a replay, **on by default**, keeping the **latest 50**.
- Recordings are stored **per player** (`recordings/<player>/`).
- **Keep a run:** a key after the round (for example K) marks it kept. Kept runs are never removed by the latest-50 limit, and they're the natural dataset for an imitation agent (5b).
- Replay your own rounds, and later compare them with agents on the same stage + seed.
- **Built** (`src/replay/recordings.py`): rounds are saved when they end, and as "stopped" on restart or quit (under 1 s: not saved). The top bar shows a red REC; after a round, the field shows the saved file and "Press K to keep it". `make recordings` lists them, `make replay_last` watches the newest, and `make maze_car_norecord` drives without recording. Only keyboard rounds are recorded; baselines use the runner (4h).

### 5. Agents

How agents are trained is flexible: imitation only, RL only, or both in either order. See [decision 012](decisions/012-agent-training-modes.md).

#### 5a. RL agent and training

**Sub-steps:** 5a1 agent core → 5a2 PPO training → 5a3 checkpoints and resume → 5a4 car health → 5a5 evaluation suite → 5a6 agent storage and history (milestone).

**Measured before planning:** torch 2.14 works in the venv. A 14 → 64 → 64 → 12 policy network (5,900 parameters) decides in 28 µs on one CPU core (9 µs measured in 5a1, with inference mode). Measured in 5a2: collection runs at 30,300 simulation steps per second (7,600 decisions per second), and training as a whole at about 5,000 decisions per second, so 1M decisions take about 3.5 min. The CPU is used, not the Apple GPU: at this size, transfers would cost more than they save.

**Settings as named files** ([decision 014](decisions/014-model-and-trainer-files.md)):
- **`models/<name>.json`** (5a1): the agent's network shape, activation, observation spec, action set, and action repeat. Picked when an agent is created, copied into the agent, and **fixed for its life**. Resuming with a different model is refused, since the weights wouldn't fit.
- **`trainers/<name>.json`** (5a2): learning rate, discount (how far ahead the agent cares), exploration bonus, rollout and batch sizes, epochs, total decisions, checkpoint interval, seed. Evaluation intervals come with the evaluation suite (5a5). **Can change at every training phase**, and each phase records which trainer it used.
- A training run = model (for a new agent) + trainer + stage + rules + reward profile.
- `agents/` is gitignored, like `runs/`.

**Milestone bar:** the agent survives most 60 s rounds and beats the heuristic's mean score (2,502) on the same seeds.

- A torch neural network drives the car through the env, and learns by trial and error over many episodes.
- **Output of training:** the weights go to the agent (`agents/<id>/checkpoints/d0100k.pt`, ...), so watching the agent picks up its newest ones (its best scored one since 5a5). The run folder holds the config, metrics, learning curve (`learning.csv`), and best replays, and records which checkpoints it wrote.
- **Pause in place:** moved to step 6 (control center), which has a window to pause from. In the terminal, Ctrl+C plus exact resume covers it.
- **Stop and resume later** (5a3, [decision 015](decisions/015-exact-resume-by-resimulation.md)): Ctrl+C, then `make resume_last`. The resumed run ends exactly as an uninterrupted one would.
- **A full checkpoint** (`runs/<run>/resume.pt`, rewritten after every update) **holds:**

  | Item | Why |
  |---|---|
  | Model weights | The learned behavior |
  | Optimizer state | Avoids a learning stutter after resume |
  | Episode/step counters, best score | Keeps metrics and replays continuous |
  | Random number generator states | Makes a resumed run identical to an uninterrupted one |
  | The current episode's seed and decisions so far | Rebuilds the game in progress by re-simulation (deterministic) |
  | Replay buffer (only for value-based algorithms like DQN, optional) | The agent's past experience. Can be tens to hundreds of MB. PPO, recommended in [decision 012](decisions/012-agent-training-modes.md), doesn't need one |

- **Branch** (5a3): `python app.py -new_agent <id> --from <agent>@<checkpoint>` makes a new agent from an old checkpoint. Train it with another trainer or reward, then compare.
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
| Survival | Share of the round survived | Step 5a5 |
| Checkpoint hunting | Checkpoints per minute | Step 5a5 |
| Braking | Stopping before walls at high speed | Step 5a5 |
| Wall control | Survival in narrow corridors | Step 7 (needs inner walls) |
| Generalization | Score on stages it has never trained on | Step 7 (needs more stages, with walls) |

- The suite runs automatically at each saved checkpoint, so skill history builds up over training.
- Changing a scenario creates a new suite version, and scores from different versions are never mixed.
- **Built in 5a5** ([decision 017](decisions/017-evaluation-suite.md)): `suites/box.json` (v1: `round` and `braking`), `make eval AGENT=id`, `make eval_baselines`. Results in `agents/<id>/evaluations/`, and the best checkpoint is what `agent:<id>` loads.

#### Agent history and storage

Goal: keep as much history per agent as possible, while files stay small and cheap to review. **Layered storage:** every event is kept, each layer only as detailed as needed.

```
agents/<agent_id>/
  profile.json      ~2 KB          current skills, lineage summary, totals. Read this first
  history.jsonl     ~200 B/event   one line per event, append-only
  checkpoints/      milestone weights only
runs/<run_id>/      per-episode detail (step 4h)
```

| Layer | Holds | Kept |
|---|---|---|
| `profile.json` | Current skill scores, lineage summary (training phases: imitation datasets and RL reward profiles), total episodes and training time, observation layout version | Always, rewritten on each change |
| `history.jsonl` | **Events, not episodes:** training phase started/ended, checkpoint saved, evaluation results, branch, settings change. Plus a summary every 100 episodes (mean/min/max reward, checkpoints, crash rate) | Forever |
| Run folder `metrics.csv` | Every single episode | Forever. Plain numbers that compress well |
| Checkpoints | Milestones only: best, latest, every Nth, and any branch point | A retention policy prunes the rest |
| Replays | New bests and evaluation episodes only, gzipped | Forever |

- Sizes, measured in 5a6: about 180 bytes per history event, a ~1 KB profile, 50 KB per checkpoint (weights), and about 1.1 MB of checkpoints per 2M-decision phase. The optimizer state lives in the run's `resume.pt` (257 KB) instead. So the retention policy is **not built yet**: every checkpoint is kept until agents grow much larger.
- **Token-efficient review:** read `profile.json` first, then only the relevant history lines. Per-episode CSVs only when needed.
- **Built in 5a6** ([decision 018](decisions/018-agent-history-and-profile.md)): `make agent AGENT=id` prints the digest (lineage, best scores next to the heuristic, score trend, totals, milestone), and `make agents` lists every agent.

#### 5b. Imitation agents

Learn to drive like a player from their recorded runs (**behavioral cloning**, a form of imitation learning).

1. **Record:** play N rounds, and keep the good ones (4i).
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

**Built in 5b** ([decision 019](decisions/019-imitation-agents.md)): `datasets/mine.json` picks your recordings, `make dataset` previews them, and `make imitate AGENT=id` clones them (`trainers/imitate.json`), then scores the clone. `make agent` shows "cloned from You (N rounds, M samples)". Measured: a clone reaches about half its teacher, and RL from a clone gets a real headstart (3,802 at 100k decisions against 5 from scratch).

### 6. Control center GUI

Separate windows, **one process per window**:

```
Control center window        Simulation window 1      Simulation window 2
(runs, curves, console)      (live play: you + AI)    (replay of run B)
        │                           ▲                        ▲
        └──── commands / metrics ───┴────────────────────────┘
                        (IPC: inter-process communication)
```

- **Control center:** runs list and status, learning curves, and a console with each job's live output. The Runs tab (6b1, [decision 023](decisions/023-runs-tab.md)) reads every run's status and curves from its folder, including runs started in a terminal.
- **Training setup:** pick the training mode (imitation, RL, or both, [decision 012](decisions/012-agent-training-modes.md)), stage, rules, reward profile, seed or seed range, and driver or starting checkpoint, then start. It's a front end over the runner (4h): the same settings a command line run takes.
- **Recordings and datasets:** browse recordings per player (4i), replay them, keep or unkeep runs, and pick kept runs as an imitation dataset (5b).
- **Everything is a named file** (stages, rules, reward profiles, recordings, runs, agents), so the control center lists and picks them rather than holding its own copies.
- **Simulation windows:** each runs its own `World` + `Renderer`, for live play or a replay. Any number can be open side by side.
- **Training runs headless in background processes**, at full speed, with no window. The control center shows their live metrics and logs.
- **Live play:** trained agents (loaded from `.pt`) drive at normal speed. It only runs agents, it doesn't train them, so it's cheap.
- **Agent roster:** agents as cards in a grid: name, mini skill radar, evaluation score, specialty (for example "box specialist"), training summary. Sort and filter by score, skill, map, or date, with a table view toggle for comparing many. Clicking a card opens its profile page.
- **Agent profile page:**
  - **Lineage:** initial training environment, then every later training phase (maps, episodes, which checkpoint it branched from).
  - **Skill radar chart:** one axis per skill from the evaluation suite, showing current levels.
  - **Skill history:** scores at each checkpoint, so you see skills grow, and sometimes drop. Further training on new environments can make an agent forget old skills ("catastrophic forgetting"), and this view reveals it.
- **Deleting into a trash:** agents (6c), runs (6b3), and later recordings (6d) can be deleted from a command or a tab. They move into `trash/` rather than being removed, since `agents/` and `runs/` are gitignored and git can't bring them back. The confirmation box lists every folder that will move, and its leaderboard place for an agent.
  - **An agent takes its own files with it:** its folder (checkpoints, history, evaluations, profile), its training and imitation runs, and the episode runs it drove (`--driver agent:<id>`). Agents branched from it are kept (they have their own copy of the weights), and their lineage shows the parent as "(deleted)". Recordings and the baselines cache are kept.
  - **A run takes only its folder:** the checkpoints it saved stay in the agent (later training continues from them; deleting the agent removes them), and the agent's history lines about it show "(run deleted)". A run still training is refused: stop it first.
  - **One trash entry per delete** (`trash/<date>_agent-<id>/`, holding every folder it moved), so **restore** puts it all back together. **Emptying the trash** is its own action with its own confirmation box.
- **Agent leaderboard:** agents ranked by **evaluation suite score**, the fair comparison (same scenarios, same seeds), plus all-time high scores per stage + rules. Training scores aren't used for ranking, because random seeds and maps make some episodes easier than others.
- **No IPC layer needed** (6a, [decision 022](decisions/022-control-center-in-pygame.md)): all state is already in files (runs, agents, recordings), so the control center reads files to show state and starts processes to act. Stop, pause, and resume are signals.
- **Why separate processes:** standard pygame gives one window per process. pygame-ce's multi-window API is NOT VERIFIED. Separate processes also mean a crashed or closed simulation window doesn't stop the control center or training.
- UI library: `pygame_gui` 0.6.14, which requires pygame-ce 2.5.3 or newer (verified in 6a).
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
- Replays embed the full stage and runs record it (4d, 4h), so experiments always point at the exact layout.
- **Map editor**, a simulation window mode:
  - Click and drag to draw walls, with snap-to-grid.
  - Place spawn points (with direction).
  - Place scripted checkpoint sequences (points in order), or choose random spawning with margins.
  - Select, move, delete, undo.
  - Save and load stage files in `stages/` (since 7d1: yours in `user/stages/`).
  - **Test drive:** switch to live play on the map being edited, then back.

**7d: map skills** ([decision 039](decisions/039-skills-suite-and-built-in-files.md)). The box-v1 suite scores every agent on the box only, so an agent trained on the arena was judged by a map it never saw, and the Runs chart mixed the two (the training line on the arena, the suite dots on the box).

| Group | Skill | Map | What it shows |
|---|---|---|---|
| Handling | Braking | box (like box-v1's braking test) | stops before a wall from full speed |
| Handling | Threading | `skill_gaps`: wall rows with gaps about 2.5 cars wide | precise steering |
| Hunting | Open field | box (like box-v1's round) | fast checkpoint hunting, no walls |
| Hunting | Long range | `skill_long`: big and empty | far checkpoints, the follow camera |
| Walls | Obstacles | `skill_pillars`: scattered pillars | steering around things |
| Walls | Corridor | `skill_corridor`: a winding path with corners and curves | following a path, checkpoints in order |
| Walls | Detour | `skill_detour`: a checkpoint behind a U-shaped wall | going around when the direct line is blocked |

- **Built-in test maps** (7d1): never edited in the app, and a map you never trained on measures skill, not memory. Training on one warns, and its skill line is marked "trained here".
- **5 episodes per skill**, the map tests with 20 to 30 s rounds: about 8 s per checkpoint (an estimate), against about 5 s for box-v1. Scores are saved per skill; today only the combined number is.
- **One scale:** each skill as a share of the heuristic's score on it, since raw points don't compare across maps. Best checkpoint: the best average share.
- **Detour will score near 0** for today's agents and the heuristic (both steer straight at the checkpoint) until the progress reward (7e).

### 8. Parallel environments

One network (one set of weights) drives N copies of the game at once, one per process. The agent doesn't learn N times over: it **collects N times more experience per second** and learns from all of it together.

1. All games send observations, and the network decides all actions **in one batched pass**.
2. Each game steps its own car, in its own process. The games don't load torch: the network stays in the training process, saving memory.
3. Results from every game go into one shared pool, and the network learns from it.

- **Synchronous** (all games step in lockstep): the same seed and the same fixed N always give the same run. A different N gives a different run (the agent sees different experience).
- **The machine decides how many:** the Training tab's number is the most; the run starts with as many as fit, drops one (after its round) when memory reaches amber or the CPU stays above 85 % for 10 s, and adds one after a calm minute. So a run follows what else you're doing and can't be re-created from its seed; each round still replays exactly.
- **4 games by default,** with memory measured (decision 038): about 0.05 GB a worker.
- **Everything that reads rounds keeps working:** metrics, Reward by term, the best replay per map, the curriculum's judging, and the Runs tab's charts.
- **Measured, not promised:** 1 game 821 decisions a second, 2 games 1,023, 4 games 984 (8a): the slowest game sets the pace, and `course_small`'s route sense recomputed its waypoint almost every decision. After that fix (8a2): 1 game 1,380, 2 games 1,807, 4 games 2,099.
- **The Training tab** gets a "Games" field (the most at once), and its time estimate follows it. The Runs tab header shows the number of games.
- **Resume:** starts fresh rounds in every game and is exact from there (no game saves its unfinished round).
- **The rollout stays 2,048 decisions in total,** split over the games (512 each with 4): updates come as often as with one game, so a run compares with a one-game run at the same decision count, and every update sees every game's map at once (today an update sees about one round on one map).
- **Mixes and the curriculum:** each new round takes the map furthest behind its share (a mix's maps even; the curriculum's shares), counted when the round starts, so games starting together get different maps. With one game, a mix's maps go in turn as before. The curriculum's level applies to all games at once.

### 9. Fuel system

- Limited fuel capacity per car. Driving uses fuel, and an empty tank ends the car's run (through `eliminate`).
- Fuel pickups are triggers with a new effect component (like checkpoints). They spawn from **their own spawn schedule and random stream** (`fuel`), so checkpoint sequences of existing seeds stay the same. Scripted stages can time fuel spawns ([decision 009](decisions/009-stage-format-and-spawn-schedules.md)).
- The observation adds the fuel level and the nearest K fuels, as a new observation version.
- Reward profiles can get fuel terms.

### 10. Multiple cars and local multiplayer

- Every car takes its `ActionInput` from a controller: keyboard, gamepad, a trained agent, or a replay.
- **Game setup lobby:** pick the stage, rules (round length, number of rounds), and seed, add agents from the roster, add human slots, then start (a simulation window opens). Setups can be saved as presets (for example "me vs top 3 agents").
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

### Later: grip and drift physics

**Why:** today a car turns at 240°/s at any speed from 120 px/s up, with no speed loss. At 300 px/s that's a turn only 72 px in radius, which would need twice the braking grip (1,250 px/s² sideways) and would skid in reality. The trained agent exploits it: it rarely drives straight (wheel centered 10 % of the time), orbits counterclockwise at nearly full speed (290 px/s on average), never brakes, and sweeps through checkpoints on the arc (36 per round, against the heuristic's 17). Measured 2026-09-27 on the box suite. Chosen for now: leave it, since it's a legitimate strategy under the current physics.

**Options, in order of size:**

| Option | What changes | Drift? |
|---|---|---|
| Grip limit (`car.grip`, for example 600 px/s²) | The tightest turn widens with speed (about 150 px radius at full speed); slow turns stay the same. Braking into corners becomes a skill | No: grip is never exceeded |
| Plus tire scrub | Hard turns also cost speed | No sliding, only the speed loss |
| Drift physics | The car's movement direction separates from its heading: sideways friction, grip that breaks loose, counter-steering. Touches movement, wall sliding, and the observation (slide angle) | Yes |

Any of these changes the physics: the behavior fixtures for turning at speed change, and agents need retraining.

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
