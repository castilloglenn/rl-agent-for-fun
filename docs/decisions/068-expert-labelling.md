# 068: Expert labelling from your takeovers

**Date:** 2026-10-02. **Status:** Accepted. Built in roadmap 7g (`CorrectionRecorder` in `src/replay/recordings.py`, the watch window in `src/envs/maze_car/demo.py`, the dataset in `src/experiments/datasets.py`, `datasets/corrections.json`, `trainers/correct.json`).

## Context

Cloning the heuristic only shows situations the heuristic gets into. A trained agent drifts into its own trouble (pushing into a wall with the checkpoint behind it) where it has no example, and RL alone can keep repeating the habit. Taking over while watching (7f9) already let you show the way out; this records it, so the agent can learn it: human-gated DAgger (the agent's own states, labelled by an expert only where the expert steps in).

## Decision

- **Recording:** watching an agent, **C** turns "REC corrections" on and off (`make correct AGENT=id`, or the Commands tab's "Correct an agent", start with it on). Every round is recorded in memory; your takeovers are marked only while it's on, and a round with any marks is saved when it ends (time up, a wreck, R, M, or closing the window), whether or not it's still on then, to `recordings/Corrections/`, the marks in its end line (`"takeovers": [[first step, last step + 1], ...]`); a round without marks isn't saved. (First built to save only if it was still on when the round ended: turning C off after correcting lost the round.) The whole round is in the file, because a replay rebuilds the agent's exact state from the start, but only the marked moments become samples. Up to 1,000 are kept. The DRIVER card says "REC corrections" (while you hold a key, "YOU are driving" still shows), and under it "this round: 2 (4 s) · saved: 3" (with it off: "C: REC corrections · saved 3"); when a round is saved, the field shows "Correction saved · 2 takeovers, 4 s" and where to find it, for 3 s. Switching maps (M) saves the round first.
- **The agent's newest checkpoint:** correcting watches the newest checkpoint, the one the next training continues, not the best one watching usually picks.
- **The dataset:** in a recording with takeover marks, only the decisions you drove become samples (the agent's view there, labelled with your keys); a recording without marks gives all its decisions, as before. A dataset can add players (`also`), and a corrected round's samples count `correction_weight` times. The built-in `corrections`: your corrections, each 10 times, with the heuristic's recordings, so the fixes don't erase the rest.
- **Learning them:** the `correct` trainer is a short, gentle imitation phase (10 epochs at learning rate 0.0003, against `imitate`'s 100 at 0.001) from the agent's newest checkpoint, so it nudges rather than overwrites what RL taught it (`make imitate_corrections AGENT=id`). Then train with RL again.
- `--corrections` is only for watching an agent: the argument check refuses it anywhere else.

## Consequences

- The weight and the epochs are starting points: if a correction doesn't stick, more epochs or a bigger weight; if the agent loses other skills, fewer.
- Your corrections are tied to the observation they were recorded with: datasets rebuild it by replaying, so they stay usable as long as the game's physics don't change.
