# 071: Being stuck costs reward

**Date:** 2026-10-02. **Status:** Accepted. Built in roadmap 7f14 (the `stuck` term in `src/envs/maze_car/rewards.py`, `StepEvents.stuck_seconds`, `rewards/default.json`).

## Context

Watching a trained agent, you saw it circle near a checkpoint for 29 s while its stuck input read 29 s. The input was right (it counts from the closest the car has been to this checkpoint, so circling can't reset it), but nothing made acting on it pay: circling keeps the car moving, so the stopped cost never applies, and progress is just 0. An input only informs; the reward has to make using it worthwhile.

## Decision

- **A `stuck` term:** 0 for the first `grace` seconds (3) without getting closer along the route than its best, then rising linearly to 1 at `full` seconds (10), and 1 after. In the default profile its weight is -0.5 per step, so being stuck costs nothing for 3 s (time to back out or turn), about -210 by 10 s, and -60 a second after: 29 s of circling costs about -1,350, nearly three checkpoints.
- It reads the same stuck timer the agent sees (`StepEvents.stuck_seconds`, from the route sense), so the input and the cost line up.
- **It can't be farmed:** it's only ever a cost, and it ends the moment the car gets 10 px closer along the route than its best. Driving the right route around walls always counts as getting closer.
- **Measured** (60 s rounds, 4 seeds, the term per round): the navigator pays 0 to -12 on every map (box, arena, the courses, `route_rooms`, `route_spiral`); the heuristic pays -49 on the box to -2,589 on `course_small`, where it gets stuck.

## Consequences

- Because it counts from the best-ever distance, coming back after overshooting a checkpoint counts as stuck until the car beats its best again; the 3 s grace covers most overshoots. The Reward by term chart shows the `stuck` line if it fires too often.
- It changes the reward: runs before this aren't comparable on totals.
