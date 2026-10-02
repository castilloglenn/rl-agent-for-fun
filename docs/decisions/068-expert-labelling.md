# 068: Expert labelling from your takeovers

**Date:** 2026-10-02. **Status:** Accepted. Built in roadmap 7g (`CorrectionRecorder` in `src/replay/recordings.py`, the watch window in `src/envs/maze_car/demo.py`, the dataset in `src/experiments/datasets.py`, `datasets/corrections.json`, `trainers/correct.json`).

## Context

Cloning the heuristic only shows situations the heuristic gets into. A trained agent drifts into its own trouble (pushing into a wall with the checkpoint behind it) where it has no example, and RL alone can keep repeating the habit. Taking over while watching (7f9) already let you show the way out; this records it, so the agent can learn it: human-gated DAgger (the agent's own states, labelled by an expert only where the expert steps in).

## Decision

- **Recording:** watching an agent, **C** turns "REC corrections" on and off (`make correct AGENT=id`, or the Commands tab's "Correct an agent", start with it on). Every round is recorded in memory; a round you took over in is saved to `recordings/Corrections/` with your stretches marked in its end line (`"takeovers": [[first step, last step + 1], ...]`); a round you didn't touch isn't saved. Up to 1,000 are kept. The DRIVER card says "REC corrections · 2 this round, 3 saved" (while you hold a key, "YOU are driving" still shows). Switching maps (M) saves the round first.
- **The agent's newest checkpoint:** correcting watches the newest checkpoint, the one the next training continues, not the best one watching usually picks.
- **The dataset:** in a recording with takeover marks, only the decisions you drove become samples (the agent's view there, labelled with your keys); a recording without marks gives all its decisions, as before. A dataset can add players (`also`), and a corrected round's samples count `correction_weight` times. The built-in `corrections`: your corrections, each 10 times, with the heuristic's recordings, so the fixes don't erase the rest.
- **Learning them:** the `correct` trainer is a short, gentle imitation phase (10 epochs at learning rate 0.0003, against `imitate`'s 100 at 0.001) from the agent's newest checkpoint, so it nudges rather than overwrites what RL taught it (`make imitate_corrections AGENT=id`). Then train with RL again.
- `--corrections` is only for watching an agent: the argument check refuses it anywhere else.

## Consequences

- The weight and the epochs are starting points: if a correction doesn't stick, more epochs or a bigger weight; if the agent loses other skills, fewer.
- Your corrections are tied to the observation they were recorded with: datasets rebuild it by replaying, so they stay usable as long as the game's physics don't change.
