# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A personal reinforcement learning playground. The first environment is **Maze Car**: a top-down pygame car with distance-sensing rays. The goal is for an agent to learn to drive it, and to make that learning visible.

The simulation is an ECS (Entity Component System), built to support walls, replay, multiple cars, and parallel envs. The first game rules (box map, car health and wall hits, timer, rewards, checkpoints) and a Gymnasium-style env API for agents are built. Stages, rules, reward profiles, replays, recordings, experiment runs, the agent core (model files, policy network, agent driver), PPO training with trainer files, exact resume, car health, the evaluation suite, and agent history are built too. The first skilled agent (the 5a milestone) is trained, and agents can also learn from your recordings (imitation). The control center has every command in a window (step 6a), a Runs tab with live learning curves (6b1), a Training tab that runs a whole training plan from one form (6b2), branching, comparing, and deleting runs into a trash from the Runs tab (6b3), an Agents tab with the roster, profiles, and leaderboard (6c), and a Files tab that edits the named files and browses recordings (6d). Step 6 is done, walls inside the field (7a: the `pillars` and `s_curve` stages), a camera for big stages (7b: follow or fit, a map card, and the `arena` stage), a map editor (7c1 and 7c2: test drive and stage size), and a Maps tab in the control center (7c3). The control center's jobs share the machine (decision 038: low priority, memory estimates, a dead switch, and every heavy job guarding itself). Built-in named files are apart from yours (`user/`) and read-only in every screen (7d1). The car's health is a bar above it (7c4). Your display settings are in `user/settings.json`, and O opens them in any game window (7c5). The default reward rewards progress along the path to the checkpoint, and +500 per checkpoint (7e, decision 041). The control center has a Settings tab for the same settings (7c6). Distances in the agent's observation use one scale on every map (7d2), and agents are scored by the skills suite: 7 skills on 6 maps, each a share of the heuristic's, the best by the average share (7d3, decision 043). Every tab stays in sync with the data (7c7). The showcase opens at once and plays any skill's map (7c8). Each scored checkpoint's driving style is measured, with warnings for bad habits (7c9). Agents can have nicknames of yours (7c10), and the Agents tab's details are in sections, with driving style as graphs (7c11). Cmd+1 to Cmd+7 open the control center's tabs (7c12). The Runs tab's second chart shows each skill's share over training, and the Agents tab's radar the 7 skills (7d4, decision 049). Training can play a map mix, its maps in turn (7d5a, decision 050), and the `skill_training` mix practices every skill on two courses plus the box and arena, never a test map (7d5b, decision 051). M picks the map to watch on, with a preview, in the game window and the showcase (7c13, decision 052). Replays say where they come from, and a mixed run keeps a best replay per map (7c14, decision 053). Agents can imitate the heuristic first, then train with RL (7c15, decision 054), and the Runs tab shows a run as soon as it starts (7c16, decision 055). Each episode keeps each reward term's sum, charted as "Reward by term" (6e, decision 056). A wall contact costs reward again only after 0.5 s clear of walls (7f1, decision 057). An easy course and mix (`course_small_easy`, `skill_training_easy`) start a manual curriculum (7f2, decision 058). Agents see 12 rays, denser in front, and the side panel shows instruments instead of fast-changing numbers (7f3, decision 059). A stopped agent must press gas or reverse (7f6, decision 060). Agents sense the way around walls (a remembered route waypoint) and how long they've been stuck (7f7, decision 061). The game window shows what the agent senses (its waypoint and route, how long it's been stuck) and thinks (a MIND card) (7f8, decision 062). A curriculum moves training up from easy to hard by itself (7f5, decision 063). Watching a driver, holding a driving key takes over for testing (7f9, decision 064). Every command checks its arguments first, and guard-rail tests run every action and make target through that check (7h, decision 065). The game window has the game on the left and the car and its AI on the right (7f10, decision 066). Following the route pays about as much as the checkpoint (progress 1.0 per px, 7f11, decision 067). Your takeovers while watching an agent can be saved as corrections and learned (7g, decision 068), and the Training tab ticks which rounds to teach, with a preview of each (7g2, 7g3, decision 074). A route-following teacher, the navigator, can be recorded and cloned; the heuristic stays the scored bar (7f12, decision 069). A clone continues with a gentler trainer, `finetune` (7f13, decision 070). Being stuck costs reward after a 3 s grace (7f14, decision 071). The Training tab trains with `finetune` up the `skills` curriculum only (7f17, decision 072). Step 7 is done. Training plays several games at once, as many as the machine has room for (8a, decision 073). A waypoint chosen close is held until the car halves the distance (8a2, decision 061). The Training tab picks the most games at once, and the Runs tab shows them (8b). Step 8 is done. The game's checkpoints are called fuel now (9a1, decision 075); saved weights are still checkpoints. Fuel works as fuel: a tank that throttle and steering burn, up to 3 fuels at once, and running dry ends a car's round (9a2, decision 076). See [roadmap](docs/roadmap.md) for what's next.

## Core commands

```
source venv/bin/activate
make help          # every command: one word, at most one parameter
make control       # the control center: every command in a window
make maze_car      # drive with the keyboard
make maze_car_heuristic
make replay FILE=path/to/replay.jsonl
make run_heuristic # a headless experiment run into runs/
make runs          # list runs
make new_agent AGENT=rookie        # an untrained agent in agents/
make maze_car_agent AGENT=rookie   # watch it drive
make train AGENT=rookie            # train it (about 7 min)
make train_curriculum AGENT=rookie # train it up the skills curriculum
make finetune AGENT=clone          # continue a clone with RL, gently
make resume_last                   # continue a stopped training exactly
make eval AGENT=rookie             # score its checkpoints, pick the best
make agent AGENT=rookie            # its digest: lineage, scores, milestone
make imitate AGENT=clone           # clone your recorded driving
make record_heuristic STAGE=basics # record the heuristic's rounds
make imitate_heuristic AGENT=clone # clone the heuristic, then train it
make record_navigator STAGE=route_lessons # record the route-following teacher
make imitate_navigator AGENT=clone # clone it, then train it
make correct AGENT=rookie          # take over where it goes wrong (saved)
make imitate_corrections AGENT=rookie # learn your corrections
make showcase AGENT=rookie         # watch its progression, checkpoint by checkpoint
make edit_map STAGE=my_map         # the map editor: draw walls, spawn, checkpoints
make recordings    # your recorded rounds (every demo round is recorded)
make vitals        # the machine's readings while the control center was open
make stop_all      # stop every job of this project (the manual dead switch)
make test
```

Full setup, including why this project uses **pygame-ce** and not `pygame`: [docs/setup.md](docs/setup.md).

## Docs

| Topic | File |
|---|---|
| Setup, commands, tests, lint | [docs/setup.md](docs/setup.md) |
| Architecture: ECS core, simulation, env, rendering | [docs/architecture.md](docs/architecture.md) |
| Config keys and how config flows | [docs/config.md](docs/config.md) |
| Geometry, physics, and code conventions | [docs/conventions.md](docs/conventions.md) |
| Game rules: rounds, rewards, checkpoints, controls, sensors, agent observation | [docs/game-design.md](docs/game-design.md) |
| Plan, step order, refactor scope | [docs/roadmap.md](docs/roadmap.md) |
| Decisions and their reasons | [docs/decisions/](docs/decisions/) |

## Rules

- Refactor steps change structure only. Behavior must stay identical, as checked by the behavior tests. New features go in their own roadmap steps.
- The physics must stay deterministic (fixed timestep, seeded randomness). Replay depends on it.
- No global state. Only `app.py` reads `FLAGS`. Systems get config through world resources, and `sim/`/`ecs/` never import `render/` or `envs/`.
- When a change makes a doc outdated, update that doc in the same change. Record new design decisions as a numbered file in `docs/decisions/`.
