# 067: Following the route pays as much as the checkpoint

**Date:** 2026-10-02. **Status:** Accepted. Built in roadmap 7f11 (`rewards/default.json`). Changes decision 041's progress weight.

## Context

agent_1, trained up the `skills` curriculum, rarely followed the route. Its runs showed why: on the maps it failed (arena: 1.9 checkpoints a minute against the heuristic's 10.3; `course_large`: 1.3 against 7.7), following the route earned +68 to +119 a round (progress, +0.1 per px closer along the drivable route), while touching walls cost about -500. Avoiding walls mattered five times more than getting anywhere, so it played safe. Level 1 was never mastered: the curriculum moved it up at its cap.

## Decision

- **The progress weight goes from 0.1 to 1.0 per px.** A 600 px leg along the route pays about +600, more than the checkpoint at its end (+500), and the route is now the main lesson. The heuristic now earns, per 60 s round: on the box +5,171 progress and +8,750 checkpoints; on the arena +6,893 and +5,750, against -52 for walls; on `course_large` +1,997 and +1,625, against -1,572.
- **Not a separate bonus for heading toward the waypoint:** it would pay for pointing the right way rather than getting closer, so wiggling in place or pinned at a wall could earn it, and it would repeat what progress measures. Progress counts the change in route distance (potential-based shaping): driving away loses exactly what driving closer earned, and reversing earns nothing, so a bigger weight can't be farmed.

## Consequences

- Agents trained before learned from the old balance (all were deleted). Run totals aren't comparable with earlier runs' (the Reward by term chart shows the terms).
- 1.0 is reasoned from these numbers, not measured on a training: if the next run trades the walls away too freely (contact and damage costs rising), 0.5 is the next try.
