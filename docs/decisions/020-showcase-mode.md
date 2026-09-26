# 020: Showcase mode, an agent's progression in the window

**Date:** 2026-09-27. **Status:** Implemented in roadmap step 5c (`src/experiments/showcase.py`, `make showcase`, `make showcase_all`).

## Context

Training leaves a checkpoint every 100,000 decisions, each scored by the evaluation suite. Numbers show progress, but watching it makes learning visible, which is the project's goal.

## Decision

- **Every checkpoint plays the same round:** the suite's first round seed, stage, and rules. You watch the same situation handled better and better.
- **Live, deterministic play instead of replay files:** a checkpoint plus a seed always gives the same game, so the window runs the agent directly. It's exactly the round the evaluation played, with no files to keep.
- **Highlights by default** (up to 8): `initial`, the first checkpoint scoring 10 % of the best, the milestone, the best, and the last, filled with evenly spaced ones. `showcase_all` shows every scored checkpoint. Unscored checkpoints are scored first.
- **A title card per checkpoint** (2 s): checkpoint and position, decisions and training time up to it (from its run's `learning.csv`), suite scores, and badges (BEST, NEW BEST, MILESTONE). A line when the round ends, then the next checkpoint. A summary at the end.
- **Controls:** the replay viewer's (SPACE pause, 1-4 speed, N step, R restart), plus Left/Right for the previous or next checkpoint. The default speed is 2×, so highlights take about 4 minutes.
- **Readable overlays:** centered messages (title cards, and the round-over text everywhere) now sit on a dark backdrop. Top bar mode labels are shortened to fit beside the HEALTH gauge.

## Consequences

- The control center (step 6) can open a showcase from an agent's profile page.
- A checkpoint's round in the showcase differs from its suite mean (it's one round of 20). The end-of-round line shows both.
