# 050: Map mixes, and courses that start anywhere

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7d5a (`src/utils/mixes.py`, `mixes/basics.json`, `src/experiments/training.py`, `src/sim/stage.py`, `src/sim/spawning.py`).

## Context

An agent trained on one map forgets the others: rookie-to-arena dropped from 5,347 to 3,325 on the box while it learned the arena. The standard cure is to keep practicing every map: one training phase that plays several. Separately, a training course (7d5b) runs through several skill zones with scripted checkpoints in order, and a weak agent that never gets past the first zone would only practice that one.

## Decision

- **A mix is a named file**, `mixes/<name>.json` (`{"format": 1, "name", "description", "stages": [...]}`), built-in in `mixes/` or yours in `user/mixes/`, edited in the Files tab ("Map mixes"). Its stages must exist. It's a file, not a list typed in the form, so one mix is reused, commands keep one parameter, and a run records it by name. The built-in `basics` mix is box, pillars, s_curve, and arena: the practice maps, none of them a `skill_` test map.
- **A mix goes wherever a stage name goes for training:** `-stage basics`, and the Train action's and the Training tab's Stage dropdown, as "mix: basics". A stage of the same name wins. Other commands (drive, watch, runs) still take stages only.
- **Maps take turns:** episode i plays map i mod n. Seeds are unchanged (episode i still uses `first_seed + i`), so training stays reproducible, and resume is exact: the run config keeps every map's full content, and the re-simulated episode is on its own map.
- **What a run records:** `config.json` gets `"mix": {"name", "stages": [full stages]}` (`null` without one), and `"stage"` stays the first map, so everything that reads one stage keeps working (watching a mixed run plays its first map). `metrics.csv` gets a `stage` column for every run. The agent's `phase_started` event gets `mix` and `stages`.
- **Display:** the Runs header says "mix basics (4 maps)", the score chart's line is "training (mixed)", the Skills chart marks every skill whose map is in the mix as trained here, the lineage says "mix basics", and the Maps tab counts a mixed run on each of its maps. High scores skip mixed runs (a run's best round could be on any of its maps).
- **The test-map warning** covers every map in a mix: "mix practice: skill_gaps is a test map: ...".
- **Scripted checkpoints can start anywhere:** a stage's checkpoints take `"start": "seeded"` (default `"first"`), and the first checkpoint is then picked from the seed, the same for every driver; the order and the loop stay. The default is left out of saved files, so the `skill_` maps and every replay are unchanged.

## Consequences

- Maps take equal turns. Weighting them (the arena twice as often) is for later, if the Skills chart shows a need.
- All maps in a mix share the phase's rules and round length, so a big map in a short round gets fewer checkpoints.
- The training line mixes maps, so it's noisier than a one-map line; the Skills chart is the fair measure.
