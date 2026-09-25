# 003: Watch learning through recorded replays, not live windows

**Date:** 2026-09-25. **Status:** Accepted, not implemented.

## Context

The first idea for watching the agent learn was to open multiple live windows. Rendering costs more than training does in this setup, so live windows slow training down.

## Decision

- Train headless at full speed.
- For each episode, record the starting state (car position, angle, maze layout, seed) plus the action at each step.
- Save the recording only if it beats the best score so far.
- A replay mode loads a recording, rebuilds the start, and feeds the actions through the same simulation, rendered at normal speed.

Format: JSON Lines, one line per step, readable as text. It can optionally include ray distances and reward per step, to inspect decisions without replaying.

## Consequences

- The simulation must stay deterministic: see [conventions](../conventions.md#determinism-must-keep).
- Parallel environments are still planned, but only for training speed, not for watching.
