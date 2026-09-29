# 035: The map editor

**Date:** 2026-09-28. **Status:** Accepted. 7c1 implemented (`src/editor/`, `make edit_map STAGE=name`); test drive and stage size follow in 7c2.

## Context

Stages are JSON files ([decision 009](009-stage-format-and-spawn-schedules.md)), and since 7a they hold walls. Writing wall rectangles by hand, and finding out only when the game loads that the spawn sits in a wall, is slow. Step 7c is an editor in a game window.

## Decision

- **A model and a window, apart:** `EditorModel` (`src/editor/model.py`) holds the stage being edited and every edit, with no drawing; `EditorWindow` (`window.py`) draws it with the game's layout and camera, and turns the mouse and keys into edits. Tests drive the model directly and the window with events.
- **Opening:** `make edit_map STAGE=name` opens `stages/name.json`, or starts a new stage from the box's size, spawn, and checkpoint rules. The control center's Play group has "Edit a map".
- **Tools:** Select (V: click to select, drag to move, drag a selected wall's corner to resize), Wall (W: drag a rectangle), Spawn (P: click to place; Q, E, or the wheel turn it 15°), Checkpoint (C: each click adds the next checkpoint in order). M switches checkpoints between random (its 40 px border margin drawn) and in order (numbered, joined by a faint line); the points come back after a switch.
- **A 10 px grid** for everything placed or moved, with faint lines every 40 px; G turns snapping off. Walls stay inside the stage.
- **Undo and redo** (Ctrl+Z, Ctrl+Y or Ctrl+Shift+Z; Cmd on a Mac): a snapshot of the stage after each finished gesture, so one drag is one undo.
- **Checked as you edit** by the game's own `Stage.from_dict`: the STAGE card says Valid, or the problem in red ("the spawn at (140, 400) is on or next to a wall (keep 16 px clear)"), and Ctrl+S refuses to save until it's valid. Stage errors now read in plain words (they printed a `Spawn(...)` before).
- **The stage file's layout:** walls one per line, the rest compact (`dump_stage`). `box.json` already looked like this; the `pillars`, `s_curve`, and `arena` files were rewritten once to match (the same content). Every stage file round-trips byte for byte.
- **The camera:** a big stage opens whole (fit); F switches to 1:1, where the arrow keys or a right-drag pan.
- **Quitting:** Esc asks first when there are unsaved changes (Enter quits, Esc goes back); with none it quits at once. The top bar says saved or unsaved.

## Consequences

- Test driving the map being edited, and changing a stage's size, come in 7c2.
- The editor edits one spawn, the first (the game uses the first).
