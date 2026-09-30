# 043: The skills suite, and the best by average share

**Date:** 2026-09-30. **Status:** Accepted. Built in roadmap 7d3 (7d3a: the 5 `skill_` maps; 7d3b: the scoring). Plans in [decision 039](039-skills-suite-and-built-in-files.md).

## Context

box-v1 scored every checkpoint on the box only: 20 full rounds and 20 braking starts. An agent trained on the arena was judged by a map it never saw, and the best checkpoint was the one with the highest mean round score.

## Decision

- **`suites/skills.json`, format 2**, is the default suite; `box.json` (format 1) is removed, with no conversion (old `box-v1.csv` files stay in agents' folders, unread). Each scenario is one skill (its `name`, `label`, and `group`), and there's no fixed shape any more (it used to need exactly one round and one braking scenario).
- **7 skills, 5 games each, fixed seeds, 25 s rounds** (braking: 3 s starts): Braking (box), Threading (`skill_gaps`), Open field (box), Long range (`skill_long`), Obstacles (`skill_pillars`), Corridor (`skill_corridor`), Detour (`skill_detour`). A skill's value is its mean game score (braking: the share of clean stops). Scoring plays with game points as the reward, so it never computes paths. The heuristic on the whole suite: 4.4 s (measured 2026-09-30); the scores it sets: Braking 1.00, Threading 697, Open field 1,096, Long range 1,070, Obstacles 132, Corridor 275, Detour 710.
- **Shares of the heuristic:** each skill's value over the heuristic's on it, the heuristic's counted as at least the skill's `floor` (100 points for a round, 0.1 for braking), so a skill the heuristic can't do can't divide by about 0. **The best checkpoint has the best average share** (ties: better survival), moved here from 7d4 because it's scoring, not display. The **milestone** ("first skilled agent") is an average share above 1.0 with under half the rounds wrecked, recorded once per suite version.
- **The overall metrics stay** (mean and worst score, checkpoints per minute, survival, wreck rate, contacts, braking), now over all rounds, so the Runs and Agents tabs keep working until 7d4 draws the skills. The leaderboard and "sort by score" rank by share; an agent's best from an older suite doesn't count (it shows unscored until `make eval`).
- **Training on a test map warns** (`src/utils/test_maps.py`, in the Training tab and `make train`), since its skill would measure memory. The box never warns: it's the map to train on.
- **The showcase** plays Open field (the box), and ranks by share.

## Consequences

- Every existing agent needs `make eval AGENT=<id>` to get skill scores (about 5 s a checkpoint), and the baselines are computed once per code version (the heuristic and random driver, about 9 s).
- The 5 test maps and the box are suite maps: protected in the Maps tab.
- Detour turned out easier for the heuristic than predicted (it slides around the U), so it isn't near 0; Obstacles (132) and Corridor (275) are its weak spots.
