# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A personal reinforcement learning playground. The first environment is **Maze Car**: a top-down pygame car with distance-sensing rays. The goal is for an agent to learn to drive it, and to make that learning visible.

The simulation is an ECS (Entity Component System), built to support walls, replay, multiple cars, and parallel envs. The first game rules (box map, car health and wall hits, timer, rewards, checkpoints) and a Gymnasium-style env API for agents are built. Stages, rules, reward profiles, replays, recordings, experiment runs, the agent core (model files, policy network, agent driver), PPO training with trainer files, exact resume, car health, the evaluation suite, and agent history are built too. The first skilled agent (the 5a milestone) is trained, and agents can also learn from your recordings (imitation). The control center has every command in a window (step 6a), a Runs tab with live learning curves (6b1), a Training tab that runs a whole training plan from one form (6b2), branching, comparing, and deleting runs into a trash from the Runs tab (6b3), an Agents tab with the roster, profiles, and leaderboard (6c), and a Files tab that edits the named files and browses recordings (6d). Step 6 is done, walls inside the field (7a: the `pillars` and `s_curve` stages), a camera for big stages (7b: follow or fit, a map card, and the `arena` stage), a map editor (7c1 and 7c2: test drive and stage size), and a Maps tab in the control center (7c3). Next: roadmap step 7d (map skills in the suite, and a progress reward around walls). See [roadmap](docs/roadmap.md).

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
make showcase AGENT=rookie         # watch its progression, checkpoint by checkpoint
make edit_map STAGE=my_map         # the map editor: draw walls, spawn, checkpoints
make recordings    # your recorded rounds (every demo round is recorded)
make vitals        # the machine's readings while the control center was open
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
