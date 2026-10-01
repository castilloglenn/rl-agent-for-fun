# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A personal reinforcement learning playground. The first environment is **Maze Car**: a top-down pygame car with distance-sensing rays. The goal is for an agent to learn to drive it, and to make that learning visible.

The simulation is an ECS (Entity Component System), built to support walls, replay, multiple cars, and parallel envs. The first game rules (box map, car health and wall hits, timer, rewards, checkpoints) and a Gymnasium-style env API for agents are built. Stages, rules, reward profiles, replays, recordings, experiment runs, the agent core (model files, policy network, agent driver), PPO training with trainer files, exact resume, car health, the evaluation suite, and agent history are built too. The first skilled agent (the 5a milestone) is trained, and agents can also learn from your recordings (imitation). The control center has every command in a window (step 6a), a Runs tab with live learning curves (6b1), a Training tab that runs a whole training plan from one form (6b2), branching, comparing, and deleting runs into a trash from the Runs tab (6b3), an Agents tab with the roster, profiles, and leaderboard (6c), and a Files tab that edits the named files and browses recordings (6d). Step 6 is done, walls inside the field (7a: the `pillars` and `s_curve` stages), a camera for big stages (7b: follow or fit, a map card, and the `arena` stage), a map editor (7c1 and 7c2: test drive and stage size), and a Maps tab in the control center (7c3). The control center's jobs share the machine (decision 038: low priority, memory estimates, a dead switch, and every heavy job guarding itself). Built-in named files are apart from yours (`user/`) and read-only in every screen (7d1). The car's health is a bar above it (7c4). Your display settings are in `user/settings.json`, and O opens them in any game window (7c5). The default reward rewards progress along the path to the checkpoint, and +500 per checkpoint (7e, decision 041). The control center has a Settings tab for the same settings (7c6). Distances in the agent's observation use one scale on every map (7d2), and agents are scored by the skills suite: 7 skills on 6 maps, each a share of the heuristic's, the best by the average share (7d3, decision 043). Every tab stays in sync with the data (7c7). The showcase opens at once and plays any skill's map (7c8). Each scored checkpoint's driving style is measured, with warnings for bad habits (7c9). Agents can have nicknames of yours (7c10), and the Agents tab's details are in sections, with driving style as graphs (7c11). Cmd+1 to Cmd+7 open the control center's tabs (7c12). The Runs tab's second chart shows each skill's share over training, and the Agents tab's radar the 7 skills (7d4, decision 049). Training can play a map mix, its maps in turn (7d5a, decision 050), and the `skill_training` mix practices every skill on two courses plus the box and arena, never a test map (7d5b, decision 051). M picks the map to watch on, with a preview, in the game window and the showcase (7c13, decision 052). Replays say where they come from, and a mixed run keeps a best replay per map (7c14, decision 053). Agents can imitate the heuristic first, then train with RL (7c15, decision 054). Step 7 is done. See [roadmap](docs/roadmap.md) for what's next.

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
make resume_last                   # continue a stopped training exactly
make eval AGENT=rookie             # score its checkpoints, pick the best
make agent AGENT=rookie            # its digest: lineage, scores, milestone
make imitate AGENT=clone           # clone your recorded driving
make record_heuristic STAGE=basics # record the heuristic's rounds
make imitate_heuristic AGENT=clone # clone the heuristic, then train it
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
