# 031: The recordings browser

**Date:** 2026-09-28. **Status:** Accepted. Implemented in roadmap step 6d2 (`src/control/recordings_view.py`, `recordings_data.py`).

## Context

Every demo round is recorded (step 4i): `recordings/<player>/`, the latest 50 kept automatically and `kept/` kept for good. They feed replays and imitation datasets (step 5b), but browsing them meant file names in a terminal, and keeping one was only possible right after its round (K).

## Decision

- **A 7th kind in the Files tab, Recordings:** the list shows players (with counts), and the right side a table instead of the editor.
- **One row per round,** newest first or by score: when, seed, score, how it ended (time, all out, stopped), kept, the game (stage, rules, round length, from the file's header, read once), and the datasets that use it.
- **"Used by" follows the dataset's rules,** judged from the file name: the player, include (all or kept), and min_score. No re-simulation, so it's instant; `make dataset` still shows what's actually usable (older physics is skipped there).
- **Watch** starts the existing "Watch a replay" action. **Keep** moves the file into `kept/`. **Unkeep** moves it back with the recent ones without pruning at once: the latest-50 limit applies at the next saved round, and a note says so, so no round vanishes by surprise. **Delete** asks first, then moves it into the trash ([decision 027](027-trash.md)).
- **Commands:** `make keep FILE=path`, `make unkeep FILE=path`, `make delete_recording FILE=path`, and matching actions in the Commands tab's Files group. The column headers have tooltips ([decision 030](030-units-and-tooltips.md)).

## Consequences

- The latest-50 limit still deletes the oldest unkept rounds for good, not into the trash. Changing that would be its own step.
- One round at a time: there's no multi-select for bulk actions yet.
