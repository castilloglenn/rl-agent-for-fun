# 045: The showcase opens at once, and plays any skill

**Date:** 2026-09-30. **Status:** Accepted. Built in roadmap 7c8 (`src/experiments/showcase.py`, `baseline_fingerprint` and `unscored` in `evaluation.py`).

## Context

Showcasing agent-1 took about 30 s with no window: before opening, the showcase scored its 2 unscored checkpoints (about 5 s each) and recomputed the heuristic's and random driver's scores (about 9 s), because their cache was tied to the exact commit and a commit had just happened. The only sign of progress was "scored ..." lines in the job's console. And it could only play Open field, on the box.

## Decision

- **The window opens at once** (`Showcase.prepare`), on the chosen skill's map, with a getting-ready card that says each step: reading the checkpoints, the heuristic's scores for this code (about 9 s, once), scoring checkpoint X, i of n (about 5 s each). The plan runs in a background thread, so the window never freezes; closing it (Esc, then Enter) stops the plan between steps. An error (an unknown agent) shows in the window.
- **The baselines' cache is keyed to a fingerprint** of only what can change their scores: the code of the simulation, the ECS, the env, the baseline drivers and scoring (`BASELINE_CODE`), the game settings in effect, and the suite with its maps and rules. A commit to the control center or the docs keeps it; changing a map it plays, or a car setting, doesn't. About 5 ms to compute.
- **Any skill:** M cycles the suite's 7 skills; each plays its own map, first seed, and round length (braking: at speed, aimed at a wall, as the evaluation's starts), so it's the round the evaluation scored. The title card shows the checkpoint's result on that skill and its share of the heuristic's. The control center's Showcase action has a Skill field (`--showcase_skill`, Open field by default); `make showcase` keeps its one parameter.

## Consequences

- Switching to a big map (Long range) resizes the window, as any big stage does.
- A fully scored agent with a fresh cache opens in under a second (measured with agent-2).
