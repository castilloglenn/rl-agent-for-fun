# 036: The Maps tab

**Date:** 2026-09-30. **Status:** Accepted. Implemented in roadmap step 7c3 (`src/control/maps_tab.py`, `maps_data.py`, `stage_preview.py`).

## Context

Stages have walls (7a), big stages get a camera (7b), and the map editor makes them (7c1, 7c2). But finding a map, seeing what it looks like, and knowing what depends on it still meant the file list. Maps will matter more with map skills (7d).

## Decision

- **A Maps tab** between Agents and Files: a card per stage in `stages/`, two per row, with a drawn preview in the stage's shape (walls, the spawn as the car with its heading, checkpoints numbered and joined in order, or random mode's border margin dashed), the name, size, and wall count, and badges: DEFAULT (the box), SUITE (a suite plays on it), BIG (bigger than the game's view). Sorted by name, newest, or walls.
- **The selected map:** a big preview, its size, walls, checkpoints, spawn, heading, and view (1:1, or followed with a map card), and **used by**: the runs that played on it, by agent or driver and kind (trained, cloned, episodes), and the suites that use it.
- **Buttons use what exists:** Edit (the map editor), Drive, and Watch a driver (the heuristic, random, or an agent's best checkpoint) on it: the Commands tab's actions, in their own windows. **New map** opens the editor on a new name (it appears here once saved). **Duplicate** copies it under a new name, in the stage file's layout. **Delete** moves it into the trash after a DELETE A MAP? box that says how many runs played on it (they keep their own copy of the stage).
- **Protected maps** can't be deleted: the box (the default the code relies on) and any stage a suite plays on. The button is greyed out, a line says why, and its tooltip too.
- **Reading:** `stages/`, `suites/`, and the runs' configs, every 2 s, so a map saved in the editor shows up without a restart.
- The Runs tab no longer assumes every folder in `runs/` is named by a run (a stray folder showed a crash in the tests).

## Consequences

- No new make targets: the buttons run existing commands, and duplicating and deleting are the same file operations as the Files tab's.
