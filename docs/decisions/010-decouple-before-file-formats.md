# 010: Decouple before the first file formats exist

**Date:** 2026-09-25. **Status:** Accepted, not implemented (roadmap steps 4a, 4c, 4f, 5, 8).

## Context

Step 4 creates the first files meant to last: stage files, replays, and run folders. Assumptions baked into them now become expensive later, because every old file would need converting or would stop working. A review found these couplings.

## Decision

Fix each where it's cheapest, most urgent first:

| # | Coupling today | Would break at | Fix | When |
|---|---|---|---|---|
| 1 | One config mixes game rules and presentation (HUD, display, window) | Tuning the HUD would make saved configs, and so replays, look changed | Split into **game-defining** keys (saved) and **presentation** keys (never saved), with a `game_config()` helper | **4a (urgent)** |
| 2 | The game score is also the agent reward | Reward experiments (step 5) would change the game score and leaderboards | Separate a **reward function** of the step's events from the game score. Default: points gained | **4a (urgent)** |
| 3 | Nothing records which code made a file | Out-of-date replays can't say when the simulation changed | A **code version** helper: git commit, plus "dirty" | **4a (urgent)**, used from 4c |
| 4 | One car per env and replay | Multi-car (step 8) would make old replays unreadable | Replays key actions **by slot**, and the header lists slots and drivers ([decision 007](007-local-multiplayer-online-ready.md)) | 4c |
| 5 | Actions are an unnamed 5-bool tuple | New actions (weapons, skills) would misread old replays | The header stores `action_names`. Actions are read by name, and missing ones count as "not pressed" | 4c |
| 6 | The driver is a label string | Can't tell which agent and checkpoint drove a replay | A **driver record** (type, id, checkpoint or device) | 4c |
| 7 | The reward function and code version aren't in run configs | Runs couldn't be compared or reproduced exactly | `config.json` records the reward function, game-defining config, and code version | 4f |
| 8 | The observation is hard-wired (8 rays, 1 compass) | Observation experiments (more rays, sensor-only) | An **observation spec** per run, recorded with its version | Step 5 |
| 9 | The HUD panels show only the first car | Several cars in one game | Choose which car the panels follow | Step 8 |
| 10 | Round state assumes 1 round per game | `game.rounds` above 1 | Per-round state and rules between rounds | When rounds go above 1 |

Already fine: time is counted in steps, randomness goes through `Rng`, stages become files ([decision 009](009-stage-format-and-spawn-schedules.md)), and the observation layout is versioned.

## Consequences

- 4a is small and changes no behavior. The behavior fixtures stay identical, and the env still returns "points gained" as the reward.
- Replay and run formats start out multi-car-ready and version-stamped, so steps 5 and 8 add data rather than change formats.
