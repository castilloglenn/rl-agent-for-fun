# 003: Watch learning through recorded replays, not live windows

**Date:** 2026-09-25. **Status:** Accepted, not implemented (roadmap steps 4c and 4d). Format refined below.

## Context

The first idea for watching the agent learn was to open multiple live windows. Rendering costs more than training does in this setup, so live windows slow training down.

## Decision

- Train headless at full speed.
- For each episode, record the starting state (car position, angle, maze layout, seed) plus the action at each step.
- Save the recording only if it beats the best score so far.
- A replay mode loads a recording, rebuilds the start, and feeds the actions through the same simulation, rendered at normal speed.

Format: JSON Lines, one line per step, readable as text. It can optionally include ray distances and reward per step, to inspect decisions without replaying.

## Refined format (planned in roadmap step 4)

Replaces "one line per step" above:

```
{"format": 1, "stage": {...full stage...}, "seed": 7, "config": {...game-defining only...},
 "slots": {"1": {"type": "agent", "id": "baseline", "checkpoint": "ep5000"}},
 "action_names": ["turn_left", "turn_right", "gas", "reverse", "brake"],
 "observation_version": 1, "steps_per_second": 120, "code": "a1b2c3d"}
{"step": 0, "actions": {"1": [false, false, true, false, false]}}
{"step": 1834, "actions": {"1": [true, false, true, false, false]}}
...
{"end": {"step": 3120, "score": 412, "reason": "all_out"}}
```

- The first line is the header. It **embeds the whole stage** ([decision 009](009-stage-format-and-spawn-schedules.md)), so a replay stays playable if the stage file changes.
- Actions are recorded **per simulation step**, but a line is written only when the action **changes**. A full 60 s round is a few KB.
- The last line stores the final step, score, and reason. Playback re-simulates and **compares**: a mismatch flags the replay as out of date (the simulation changed since recording), instead of showing wrong driving.
- Per-step extras (rays, reward) aren't stored. Replay re-simulates them exactly.
- Slots, named actions, the driver record, and the code version come from [decision 010](010-decouple-before-file-formats.md).

## Consequences

- The simulation must stay deterministic: see [conventions](../conventions.md#determinism-must-keep).
- Parallel environments are still planned, but only for training speed, not for watching.
