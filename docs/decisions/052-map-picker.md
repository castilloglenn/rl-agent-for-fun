# 052: Pick the map in the game window

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7c13 (`src/render/map_picker.py`, `src/render/renderer.py`, `src/envs/maze_car/demo.py`, `src/experiments/showcase.py`; `stage_preview.py` moved to `src/render/`).

## Context

Watching a checkpoint drive (the Runs tab's "Watch it drive", or Watch an agent) opened on one map, and seeing it on another meant closing the window and starting again. Showcase's M cycled the skills one by one, so reaching the sixth meant five presses.

## Decision

- **M opens a MAPS box** over the field: a list on the left (the map playing now marked "(now)", yours tagged "yours"), and on the right a preview of the highlighted map (walls, spawn, checkpoints in order) with a caption ("1300 × 700 · 11 walls · scripted, 9 checkpoints, any start"). Up and Down pick, Enter plays it, Esc or M closes. The game waits while it's open. A long list scrolls with the pick.
- **Watching a driver** (an agent or the heuristic) lists every stage, built-ins first, then yours. Picking one starts a fresh round there with the same driver and checkpoint, in a window sized for that map.
- **Showcase** lists the suite's skills with their maps ("Threading · skill_gaps"), since it plays each skill's own round (braking's start at a wall too). Picking one replays the current checkpoint on that skill, from its card. It replaces M's cycling.
- **Not while you drive** (it would cut a recording short), and not in the map editor's test drive (it's for the map being edited). There, M does nothing.
- **One preview drawing:** `draw_stage_preview` moved from `src/control/` to `src/render/`, so the game window can use it without importing the control center. The Maps tab uses it from there.
- The shortcuts box (?) lists M wherever the window offers maps.

## Consequences

- Each pick builds a new game and window, like the showcase's skills did: the window resizes for a big map, and its overview plays first.
- Keys only, like the O box: no mouse.
