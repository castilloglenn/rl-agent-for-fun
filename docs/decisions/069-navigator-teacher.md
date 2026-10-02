# 069: The navigator, a teacher that follows the route

**Date:** 2026-10-02. **Status:** Accepted. Built in roadmap 7f12 (`src/drivers/navigator.py`, `datasets/navigator.json`, `make record_navigator`, `make imitate_navigator`).

## Context

The heuristic still drives with what it had from the start: a straight compass to the checkpoint and the three front rays at 0 and ±45 degrees. It aims through walls (0.8 checkpoints a minute on `course_small`) and turns away from narrow gaps, and clones inherit that. Upgrading it would move the 1.0 bar every skill, milestone, and curriculum goal is measured against.

## Decision

- **A second hand-written driver, `navigator`, as a teacher only.** The heuristic stays the scored bar; the navigator is never scored, it's recorded for cloning.
- **What it does differently:** it steers at the remembered route's waypoint (7f7) instead of the checkpoint; judges the way ahead with the narrow front rays (0 and ±15 degrees), so it fits through gaps; slows right down when the waypoint is behind it (a tight turn in a lane); with a wall ahead, turns toward the waypoint's side if that side has room; and when the stuck timer passes 2 s with a wall in front, backs out for 0.75 s with the wheel turned so the front swings toward the waypoint.
- **Measured** (60 s rounds, 6 seeds, checkpoints a minute, heuristic → navigator): box 19.0 → 27.0, arena 12.5 → 18.7, pillars 10.2 → 21.0, s_curve 13.0 → 15.0, `course_small_easy` 24.0 → 58.0, `course_large` 6.9 → 21.7 (wrecks 2 → 0), `course_small` 0.8 → 20.5, and on the test maps skill_detour 8 → 11, skill_gaps 4 → 4, skill_corridor 1 → 12, skill_pillars 9.1 → 14.5 (wrecks 3 → 1). Its first version lost on the easy course (24 → 3, it overshot a turn in a lane and looped backing out): the behind-speed, the waypoint-side turn, and the backing direction fixed that.
- **Recording and cloning:** `make record_navigator STAGE=...` (default `skill_training_easy`) records it to `recordings/Navigator/`; the `navigator` dataset clones it (`make imitate_navigator AGENT=id`, or the Training tab's dataset). The `corrections` dataset now mixes your corrections with the navigator's driving instead of the heuristic's: the two teachers disagree at narrow gaps.

## Consequences

- Clones of the navigator can beat the heuristic on every skill from the start, so the curriculum's level 1 goal (beat the heuristic) comes sooner.
- The `corrections` dataset needs the navigator's recordings (record it first).
