# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A personal reinforcement learning playground. The first environment is **Maze Car**: a top-down pygame car with distance-sensing rays. The goal is for an agent to learn to drive it, and to make that learning visible.

The simulation is an ECS (Entity Component System), built to support walls, replay, multiple cars, and parallel envs. The first game rules (box map, crash, timer, rewards, checkpoints) and a Gymnasium-style env API for agents are built. No agent is trained yet. Next: roadmap step 4 (stages, replays, and experiment runs). See [roadmap](docs/roadmap.md).

## Core commands

```
source venv/bin/activate
make maze_car      # human-driven demo: WASD/arrows, Esc quits
make run           # agent entry point (stub)
make test          # python -m pytest
make replay FILE=path/to/replay.jsonl   # watch a replay
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
