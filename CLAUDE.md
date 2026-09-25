# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A personal reinforcement learning playground. The first environment is **Maze Car**: a top-down pygame car with distance-sensing rays. The goal is for an agent to learn to drive it, and to make that learning visible.

The RL side is not built yet. Current work: a structure-only refactor into an ECS (Entity Component System), to prepare for walls, replay, multiple cars, and parallel envs. See [roadmap](docs/roadmap.md).

## Core commands

```
source venv/bin/activate
make maze_car      # human-driven demo: WASD/arrows, Esc quits
make run           # agent entry point (stub)
make test          # python -m pytest (behavior tests)
```

Full setup, including why this project uses **pygame-ce** and not `pygame`: [docs/setup.md](docs/setup.md).

## Docs

| Topic | File |
|---|---|
| Setup, commands, tests, lint | [docs/setup.md](docs/setup.md) |
| Current architecture (pre-refactor) | [docs/architecture.md](docs/architecture.md) |
| Geometry, physics, and code conventions | [docs/conventions.md](docs/conventions.md) |
| Plan, step order, refactor scope | [docs/roadmap.md](docs/roadmap.md) |
| Decisions and their reasons | [docs/decisions/](docs/decisions/) |

## Rules

- Refactor steps change structure only. Behavior must stay identical, as checked by the behavior tests. New features go in their own roadmap steps.
- The physics must stay deterministic (fixed timestep, seeded randomness). Replay depends on it.
- Don't add new dependencies on `StateSingleton`, `FieldSingleton`, or global `FLAGS` reads. They are being removed.
- When a change makes a doc outdated, update that doc in the same change. Record new design decisions as a numbered file in `docs/decisions/`.
