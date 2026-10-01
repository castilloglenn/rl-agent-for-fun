# 063: An automatic curriculum

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7f5 (`src/utils/curricula.py`, `src/experiments/map_baselines.py`, `curricula/skills.json`, the curriculum in `src/experiments/training.py`, level marks in `src/control/charts.py` and `runs.py`).

## Context

Training easy to hard (7f2) by hand means watching the Skills chart and starting the next phase yourself; you wanted it automatic and built before the next training, with the rule "when it beats the heuristic and levels off, move on", keeping earlier maps against forgetting.

## Decision

- **A curriculum is a named file** (`curricula/<name>.json`, built-in or yours in `user/curricula/`, edited in the Files tab): levels in order, each a mix (or one stage) with a goal, a minimum stay, and an optional cap; how much of the episodes earlier maps keep (`earlier_share`); and the smoothing window. It goes wherever a stage or a mix goes for training ("curriculum: skills"; a stage or mix of the same name wins). The built-in `skills`: `skill_training_easy`, then `skill_training`.
- **Judged on the training maps, never the test maps:** on each map of the level, the agent's checkpoints a minute over its last 20 episodes there, as a share of the heuristic's on that map (measured once per map and rules, 3 rounds, cached in `agents/baselines/maps.json` under a hash of the simulation and baseline code, the game settings, the map, and the rules; at least 1 a minute counts, so a map the heuristic can't do doesn't divide by about 0).
- **Moving up:** after the level's minimum (200k decisions), when every map reaches the goal (1.0: beats the heuristic) and has leveled off (its last 20 episodes no more than 2 % better than the 20 before); or at the cap (1.5M) anyway. The last level is where it stays.
- **Earlier maps stay:** maps only earlier levels had keep `earlier_share` of the episodes (a quarter), the level's maps share the rest, evenly. Each episode plays the map furthest behind its share: deterministic.
- **Seen and resumable:** the level is in `learning.csv` (a `level` column) and in the agent's history (`level_up`: level, why, decisions); a new phase on the same curriculum picks up at the agent's last level. The run's config keeps the curriculum, its maps per level, and the heuristic's rates; the resume state keeps the level, its counts and recent rates, and the current episode's map, so a resume is exact even across a level change. The Runs header says "curriculum skills · level 2 of 2", and the charts mark each level up with a dashed vertical line. `make train_curriculum AGENT=id` trains on `skills`.

## Consequences

- The first curriculum training on a set of rules measures the heuristic on each map before it starts (about 30 s with 60 s rounds, a minute with 120 s; the Runs tab's starting row says which map), then it's cached.
- The goals are guesses until a run shows realistic numbers (7f4): the minimum, the cap, and the window are in the file to tune.
