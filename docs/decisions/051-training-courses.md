# 051: Training courses instead of one training map per skill

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7d5b (`stages/course_small.json`, `stages/course_large.json`, `mixes/skill_training.json`).

## Context

A mix (decision 050) keeps an agent practicing several maps. To practice every skill without training on its `skill_` test map, the first plan was one training map per skill (`train_gaps`, `train_corridor`, `train_detour`, a big empty map). You asked for fewer maps that each train several skills in sequence.

## Decision

- **Two courses**, each a loop of scripted checkpoints through several skill zones, with a seeded start (`"start": "seeded"`), so a weak agent that never finishes a lap still practices every zone:
  - `course_small` (1300 × 700, 9 checkpoints): two wall columns with one 48 px gap each (Threading), a U that opens downward with a checkpoint inside, met from its side (Detour), a lane that winds up and down, 110 to 160 px wide (Corridor), and a return lane along the bottom.
  - `course_large` (1800 × 1200, 11 checkpoints): a field of 16 pillars in an offset grid (Obstacles), a lane with 4 turns going down, 160 px wide (Corridor), and a long straight back west with checkpoints 700 px apart (Long range).
- **Unlike the test maps:** the gaps are wider and at other heights than `skill_gaps`', the U opens another way than `skill_detour`'s, the lanes run another way than `skill_corridor`'s, and the pillars are another grid than `skill_pillars`'. Every passage is at least as wide as its test map's.
- **The `skill_training` mix:** box (Open field, and Braking in its turns), arena (Long range among walls), `course_small`, and `course_large`. No `skill_` map, so the test-map warning stays quiet.
- **Checked:** a test drives a path (the progress reward's path field) from the spawn and from each checkpoint to the next on every built-in scripted stage.

## Consequences

- The heuristic steers straight at the checkpoint, so it does poorly on the courses (1 checkpoint a round on `course_small`). That doesn't matter: the courses are for training, and the suite still scores on the `skill_` maps.
- A lap is longer than a 60 s round for a slow agent; the seeded start spreads the practice over the zones instead.
- If the Skills chart shows a skill lagging, a course can be weighted or a zone added.
