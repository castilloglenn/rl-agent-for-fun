# 058: An easy training course, for a manual curriculum

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7f2 (`stages/course_small_easy.json`, `mixes/skill_training_easy.json`).

## Context

On `course_small` (decision 051) every leg between checkpoints crosses walls, and the heuristic, the heuristic's clone, and both trained agents collected 0 checkpoints: a quarter of `skill_training`'s rounds only ever cost reward, which taught agent_2 to do less (decision 057). A learner needs reward it can find first, then harder maps: a curriculum, easy to hard, keeping earlier maps in the mix against forgetting.

## Decision

- **Two levels, as map files:** `course_small_easy` (easy) next to `course_small` (hard), not a level setting in the engine yet: breadcrumbs added automatically for any map would change its game score (more checkpoints) and need the level in the map's identity. Worth it only if easy clearly helps.
- **Easy means breadcrumbs and room:** the same layout (two gap columns, the U, the winding lane, the return lane), with 80 px gaps (48 on hard), lanes about 150 px wide (110 to 160 on hard), wider turns, and 28 checkpoints (9 on hard), each in a straight line from the one before with at least 24 px from any wall for the car (a test checks every leg). It starts at the first checkpoint, beside the spawn: with a seeded start the fixed spawn is far from most first checkpoints, the leg crosses walls, and a weak driver gets nothing.
- **Why the wider passages:** with breadcrumbs only (48 px gaps), the heuristic still got 1 checkpoint a round. Its wall rule turns away when a front diagonal ray sees a wall within about 78 px, and facing a gap head-on both diagonals see the gap's walls within about 55 px of it: it can't drive through a gap narrower than about 110 px head-on (it gets through `skill_gaps` at an angle). With 80 px gaps it got 14 of 28; with the lanes widened too, 24 of 28 in a 60 s round and 29 (a whole loop) in 120 s, reward +11,580 and +14,205. A clone of the heuristic inherits that turning away from narrow gaps; RL has to unlearn it on the hard level.
- **The mix `skill_training_easy`:** box, arena, `course_small_easy`, `course_large`: the first level. Then `skill_training` (with `course_small`) once the Skills chart levels off (7f4, by hand; 7f5 automates it later).

## Consequences

- The `skill_` test maps don't change, so scores stay comparable.
- The heuristic's gap limit matters for the rays decision (7f3): more rays change what an agent can see, not what the heuristic (and so a clone) does.
