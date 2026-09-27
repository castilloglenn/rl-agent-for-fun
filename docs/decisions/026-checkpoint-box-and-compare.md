# 026: Acting on a checkpoint from its dot, and comparing two runs

**Date:** 2026-09-28. **Status:** Accepted. Implemented in roadmap step 6b3 (`src/control/runs_tab.py`, `charts.py`).

## Context

The Runs tab's score chart shows each checkpoint's suite score as a dot ([decision 023](023-runs-tab.md)). Watching or branching from a checkpoint still meant typing `agent@checkpoint` into another action, and there was no way to see two runs' curves together.

## Decision

- **Click a suite dot** (within 9 px): a small box opens by it with the checkpoint (`rookie@d1700k`), its suite score and decisions, and two buttons. The dot gets a white ring. Esc, or a click elsewhere, closes it; Esc closes the box before it would ask to quit.
  - **Watch it drive** starts the Commands tab's "Watch a driver" with `agent:<id>@<checkpoint>` (a game window).
  - **Branch from it** opens the Training tab set to RL for a new agent, with Start `<id>@<checkpoint>`, the name field focused.
  - The buttons are drawn by hand and act on release, like the confirmation box.
- **Charts report where they drew** (`draw_chart` returns a `Plot` with its area and mapping), so a click finds the nearest dot.
- **Compare with:** a dropdown at the top right of the run lists the other runs of the same kind. The compared run's lines join both charts in a muted orange (a second line in gray), labeled with its agent and start time ("clone 01:48"). On the score chart only its lines join, not its suite dots, so the selected run stays readable; the second chart also takes its dots (episode runs plot dots there).
- **The x axis stays the agent's total decisions:** two runs from scratch line up, and a branch's run continues where its parent stopped.
- **A full legend drops its least useful items first** (a series `priority`: the best ring, then the heuristic level), instead of running into the title.

## Consequences

- Only one run at a time can be compared. More would need a legend of its own.
- The suite dots can only be clicked for training runs (imitation and episode runs have none).
