# 054: Imitate the heuristic, then train with RL

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7c15 (`src/experiments/driver_rounds.py`, `datasets/heuristic.json`, the "Record a driver's rounds" action, `make record_heuristic`, `make imitate_heuristic`).

## Context

An agent learning from scratch spends its first million decisions finding out that driving toward the checkpoint pays. Imitation (5b) and the "Imitation, then reinforcement learning" mode existed, but imitation only learned from recordings, and only rounds you drive with the keyboard were recorded. The heuristic is the bar every skill is measured against, and it decides from the same observation the agent gets, so its driving can be cloned exactly (yours uses what you see on screen).

## Decision

- **Record any driver's rounds** (`record_rounds`, `-record_rounds <driver> --rounds N`, the Commands tab's "Record a driver's rounds"): it plays the driver headless and saves every round to `recordings/<Player>/` (the heuristic: `recordings/Heuristic/`), exactly like your rounds, so the dataset code needs no change. Not the keyboard (it needs the window).
- **A stage or a mix:** a mix plays its maps in turn, one per round. Round i uses seed first_seed + i; the suite's seeds start at 1,000,000, so a recorded round is never a test round. Recording on a `skill_` map warns, as training does.
- **The library keeps at least the rounds asked for** (`limit = max(50, rounds)`), so recording 200 doesn't prune 150 of them.
- **A built-in dataset `heuristic`** (player "Heuristic", all rounds), so "Imitation, then reinforcement learning" with dataset `heuristic` clones the heuristic, then trains with RL.
- `make record_heuristic STAGE=basics` (the default: box, pillars, s_curve, arena) and `make imitate_heuristic AGENT=id`.

## Consequences

- 50 rounds take about 26 s to record and give about 89,000 samples; building the dataset (re-simulating them) takes about as long again when imitation starts.
- A clone starts near the heuristic (an average share near 1.0, usually a bit under); RL has to take it past.
- The heuristic is weak on mazes (1 checkpoint a round on `course_small`), so record it on open maps and let RL learn the courses.
- Recording takes a stage or a mix, not a curriculum (7f5): a curriculum's hard levels would teach a clone the heuristic's stuck habits, so it's refused with the first level's mix to use instead, and the Record action's Stage list leaves curricula out.
- Its recordings show up wherever recordings do (the Files tab's browser, high scores per stage), as player "Heuristic".
