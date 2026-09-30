# 039: A skills suite, and built-in files apart from yours

**Date:** 2026-09-30. **Status:** Accepted, planned (roadmap 7d1 to 7d4, and 7e).

## Context

- **One suite, one map.** box-v1 scores every agent on the box. Two agents trained on the arena on 2026-09-30 showed the gap: arena-rookie (from scratch) and rookie-to-arena (branched from rookie@d1700k) ended level on the arena (about 1,170 and 1,190 game points in their last 200k decisions), but the suite could only say how they drive on the box. rookie-to-arena's "best" is its starting point (rookie's own checkpoint), because it lost box skill (5,347 to 3,325) while learning the arena. The Runs chart showed the arena training line and the box suite dots on one axis, without naming either map.
- **The distance scale changes with the map.** `src/sim/observation.py` divides rays and the checkpoint distance by the current field's diagonal: 978 px on the box, 1,697 px on the arena. The same input means a different distance on each map, so skills measured on maps of different sizes aren't comparable.
- **Built-ins and your files are mixed.** Every named-file folder (stages, rules, rewards, trainers, models, datasets, suites) is in git, and the app can edit and delete all of them. Leaderboards group by rules name and suites are the ruler agents are measured by, so a changed built-in silently changes old results. Your own map (ruins) sits in git as if it were one of the app's defaults.

## Decision

1. **Built-in and your files (7d1).** Built-ins ship with the app, are committed, and are read-only in every screen: they change only in code. Everything you make in the app goes to `user/<kind>/`, out of git. One name per kind: yours can't reuse a built-in's, so runs, replays, and leaderboards keep resolving by name. A built-in offers Duplicate (a copy in `user/`) instead of Edit and Delete. Future built-ins follow the same split, for example battle arenas, battle rules, and opponent agents for a battle mode.
2. **A fixed distance scale (7d2):** 978 px for every map, clipped at 1. On the box it gives the same numbers, so box agents and the behavior tests don't change.
3. **A skills suite (7d3):** 7 skills in 3 groups (the table in the roadmap's step 7), on the box and 5 new built-in `skill_` maps, 5 episodes each, scored per skill at every checkpoint. It replaces box-v1 for new scores; box-v1's history stays.
4. **Skills chart and radar (7d4):** one line per skill, as a share of the heuristic's score on it; best checkpoint = the best average share; the Agents tab radar shows the same 7 skills, so "skill" means one thing.
5. **Training on a test map warns, it isn't blocked.** Its skill line is marked "trained here".
6. **The progress reward around walls moves to its own step (7e).**

7d1a note: `datasets/mine.json` stays built-in. It was added with imitation (step 5) as the app's default dataset ("all rounds by player You"), not a selection of yours, and the code defaults to it; datasets you make go to `user/datasets/`. A name found nowhere gives the loaders the built-in path, so each still reports a missing file its own way.

## Consequences

- Scoring takes about 8 s per checkpoint instead of about 5 s (an estimate, to be measured).
- The two arena agents were trained with the old scale, and would need retraining to benefit from 7d2.
- Detour will score near 0 until 7e, which is the point: it shows the gap.
