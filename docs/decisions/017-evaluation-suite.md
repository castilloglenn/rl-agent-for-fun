# 017: The evaluation suite, and watching the best checkpoint

**Date:** 2026-09-27. **Status:** Implemented in roadmap step 5a5 (`src/experiments/evaluation.py`, `suites/box.json`, `make eval`).

## Context

Training metrics come from sampled play on training seeds, so they are noisy and flattering. Agents and checkpoints need one fair, fixed test. The last checkpoint also isn't always the best: in 5a4, an agent at 1.5M decisions beat the same agent at 2M.

## Decision

- **A suite is a file**, `suites/<name>.json`, with a `version`. Changing a scenario means a new version, and scores from different versions are never mixed (one results file per version).
- **Two scenario kinds** in `box` v1:

  | Scenario | Setup | Metrics |
  |---|---|---|
  | `round` | 20 full rounds, `standard` rules, seeds from 1,000,000 | Mean and worst score, checkpoints per minute alive, share of round survived, wreck rate, wall contacts per round |
  | `braking` | 20 starts at 300 px/s aimed at a wall, 80 to 140 px away, up to 30° off head-on (wall, distance, angle, and spot from the seed), 3 s each | Share of starts with no damage, by braking or steering away |

- **Seeds never overlap training**, which uses seeds from `--seed` (0) upward.
- **Deterministic play:** agents take their top action, so a checkpoint always gets the same scores. The heuristic and random baselines play the same suite as reference rows.
- **Results:** `agents/<id>/evaluations/<suite>-v<version>.csv`, one row per checkpoint. The **best checkpoint** is the highest mean round score (ties: better survival), saved in `evaluations/best.json` for the default suite.
- **Scored during training:** the trainer's `evaluate` (default true) scores each saved checkpoint, printed as one line. It plays separate games with its own driver, so the training numbers and exact resume don't change. About 4 to 5 s per checkpoint (+20 % on a 2M training).
- **Watching loads the best:** `agent:<id>` (and `make maze_car_agent`) loads the best scored checkpoint, else the newest. `@best` and `@<name>` pick one explicitly. Training always continues from the newest.

## Consequences

- The braking distance was tuned before v1 was fixed: at 150 to 250 px, the random baseline passed 80 % (too easy). At 80 to 140 px (pure braking takes 75 px), random passes 5 %, the heuristic 100 %, and the 5a4 agent 90 %.
- An untrained agent can pass braking by chance (its top action may be the brake), so braking is a secondary metric. The round score picks the best checkpoint.
- Wall control and generalization scenarios need inner walls and more stages (step 7). They arrive as new suite versions.
