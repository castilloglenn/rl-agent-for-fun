# 049: The Skills chart and radar

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7d4 (`src/utils/skills.py`, `src/control/runs.py`, `src/control/charts.py`, `src/control/agents_data.py`, `src/control/agents_tab.py`).

## Context

Since 7d3 an agent is ranked by its average share of the heuristic's score across the 7 skills, but the Runs tab's main chart still showed game points, and the Agents tab's radar still had the old six axes (score, survival, hunting, braking, intact, clean), relative to the best agent. Neither showed which skills a run improves, or whether training on one map costs another.

## Decision

- **The Runs tab's main chart is SKILLS** for a training run: one line per skill, each its share of the heuristic's score on that skill (1.0: as good as the heuristic), over the run's scored checkpoints. The average share (the ranking) is dots you can click (watch, branch), the best is ringed, and the heuristic is a dashed level at 1.0. A skill whose map is the one the run trains on is dashed and labeled "(trained here)". The title names the map: "SKILLS · trained on pillars".
- **The game score moved to the second chart** as its first option, "Training score", titled with the map it's on. It's the score on the training map only, so it no longer sits next to the suite.
- **Compare** adds the other run's average share dots, not seven more lines.
- **A full legend wraps** (`Chart.legend_rows`): past the header row, full-width rows under it, only as many as it needs; the plot shrinks by them. The Skills chart allows 3.
- **The radar shows the 7 skills** as shares, with the rim at 1.5 times the heuristic (`agents_data.RADAR_RIM`) and the heuristic's outline at 1 / 1.5 of the way, so an agent past the heuristic shows it. A share above 1.5 is clipped to the rim. The cards' mini radar is the same.
- **The skill history** offers the average share and each skill's share first (a dashed level at 1.0), then the old metrics. "Braking" (a raw rate) is gone: the Braking share replaces it.
- **One place for the skills:** `src/utils/skills.py` (no torch) loads the suite's skills and computes shares; the evaluation, the Runs tab, and the Agents tab all use it.

## Consequences

- Scored events without a "share" (from before 7d3) don't show; per the first-version rule, rescore or delete such agents.
- "Trained here" compares one stage name. 7d5 (mixed-map training) gives a run several maps, so it will need to mark each skill whose map is in the run's list.
