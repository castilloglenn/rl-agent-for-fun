# 053: Where a replay comes from, and a best replay per map

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7c14 (`src/replay/source.py`, `src/replay/viewer.py`, `src/render/panels.py`, `src/experiments/training.py`, `src/experiments/runs.py`, the spinner in `src/render/renderer.py`).

## Context

The replay window named the driver and the map, but not where the replay came from: which run, which episode, how far training was. And since mixed training (7d5), a run's "best replay" was the best game score on any map, which leans toward the maps that score more, so the other maps' best rounds were never kept. Separately, the showcase's "Getting ready" card was easy to miss.

## Decision

- **A SOURCE card** in the replay window, in place of the one-car leaderboard (which only repeated the score): From (training, a run, or your recording, kept or not), the run (short: "train-agent_1 · 10-01 12:23"), the episode (as in the file's name), how many decisions training had made then, and the mix it was played in. Your recording shows the player and when it was recorded. All of it comes from the replay's header and file path (`source_rows`).
- **A best replay per map:** training saves a replay when an episode beats the best on its own map (`best_by_map`, kept in the resume state), so a mixed run keeps each map's best. A one-map run saves exactly as before.
- **Watching a run's best replay** plays the overall best, as before. For a mixed run, M opens the MAPS box (decision 052) with each map's best ("course_small · best 145") and its preview; a pick plays that one. `best_replays(run)` lists them.
- **A spinner** (a ring of dots, the brightest going round) above the message box while the showcase gets ready (`ModeInfo.busy`). It stops when there's an error or nothing to show.

## Consequences

- A run resumed from a resume state saved before this keeps no per-map bests yet, so its next episode on each map saves a replay. That's harmless.
- Runs trained on a mix before this kept only new overall bests, so M lists only the maps that happened to set one.
