# 055: Runs that are still starting

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7c16 (`src/control/runs.py`, `src/control/runs_tab.py`, `src/render/spinner.py`, `build_dataset`'s progress in `src/experiments/datasets.py` and `imitation.py`).

## Context

The Runs tab lists a run once its folder has a `config.json`. A training writes it about 1 s after it starts, but an imitation builds its dataset first: 52 s for 50 heuristic rounds at low priority (the vitals log of the first "Imitation, then reinforcement learning" plan: Start at 13:50:43, the imitation run's folder at 13:51:37). Meanwhile the tab kept showing the run selected before, so nothing seemed to happen.

## Decision

- **A starting row** at the top of the list for each of our running jobs that will write a run but hasn't said its folder yet: a training, imitation, or episode run (by its command's flag), or a Training tab plan's step before its first run (creating the agent: the row takes the kind of the first step that makes a run). Its status is "starting" (accent color), its time is when the job started, and it's live (an agent starting a run is busy; it can't be deleted).
- **The tab follows it:** a plan just started selects its starting row at once, and moves on to the real run when the job says its folder.
- **The starting view:** the job's name, a spinner (the showcase's, now shared in `src/render/spinner.py`), the job's latest output line, the time so far, the plan's next steps ("Then: Train agent_2 ..."), and that the charts come once the run starts. Stop and Pause work already; compare, delete, and the charts wait for the run.
- **Imitation says how its dataset goes:** "Building the dataset: round 21 of 50", every 5 rounds, so the starting view shows progress instead of a frozen line.

## Consequences

- Nothing on disk changes: starting rows exist only while our job runs. A run started in a terminal still appears when its folder does.
- A resumed run already has its folder, so it never shows a starting row.
