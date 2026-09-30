# 042: One distance scale on every map

**Date:** 2026-09-30. **Status:** Accepted. Built in roadmap 7d2 (`DISTANCE_SCALE` in `src/sim/observation.py`).

## Context

The observation divided rays and the checkpoint distance by the current field's diagonal: 980.5 px on a box-sized map, 1,697 px on the arena. So a wall 100 px away read 0.10 on the box and 0.06 on the arena, and 0.06 means 58 px on the box: the same number meant a different distance on each map. The heuristic reads the same numbers (it turns away from walls closer than 0.05), so its margins changed with the map too. Skills measured across maps (7d3) wouldn't be comparable.

## Decision

- **One scale, 980.5 px** (`math.hypot(855, 480)`, the box's diagonal), on every map, clipped at 1: farther than that reads "far".
- **A code constant, not a config key:** it defines what the agent's inputs mean, like the rest of the observation layout, so a run can't quietly change what a trained agent sees.
- **The observation version stays 1:** on a box-sized map the numbers are the same to the bit (the behavior tests pass unchanged). No compatibility code: agents that learned the old scale on bigger maps are simply out of date, and can be deleted or retrained.

## Consequences

- **Out of date:** the two agents trained on the arena, `arena-rookie` and `rookie-to-arena` (its arena phase). On the arena they now see different numbers than they trained on. `rookie` and `clone` (box-trained) are unaffected.
- **Unaffected:** your recordings and datasets (imitation re-simulates them, so observations are computed fresh), runs and replays (the observation isn't recorded or verified), the box suite and its heuristic baseline.
- **The heuristic** keeps its thresholds, so on the arena it now brakes and turns at the same px distances as on the box (49 px instead of 85 px for its wall margin).
