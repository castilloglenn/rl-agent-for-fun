# 027: Deleting into a trash, with restore

**Date:** 2026-09-28. **Status:** Accepted. Runs implemented in roadmap step 6b3 (`src/control/trash.py`, `src/control/confirm.py`); agents follow in 6c.

## Context

Runs and agents are local data in gitignored folders, so a mistaken `rm` can't be undone with git. Deleting also has links to respect: a run's checkpoints live in its agent, and an agent's history names its runs. The roadmap's step 6 lists the rules.

## Decision

- **Deleting moves, into `trash/`** (gitignored): one entry per delete, `trash/<date>_<time>_run-<folder>/`, holding each moved folder at its path from the repo root, plus a `trash.json` (kind, label, when, the paths).
- **A run takes only its folder.** Its checkpoints stay in the agent (later training continues from them), and the agent's history keeps its lines about it; the agent digest (`make agent`) shows "(run deleted)" for its phase. A run still running (its lock is alive, or it wrote in the last 30 s) is refused.
- **Restore** puts every folder of an entry back and removes the entry. It's refused, keeping the entry, if something has one of those names again.
- **Emptying** deletes every entry for good.
- **Asking first, in the control center:** a generic confirmation box (`confirm.py`, the QUIT? box made reusable) with Cancel (Esc) and a red-titled Delete (Enter). An action asks first when it has a `confirm` (Delete a run, Empty the trash). Closing the window while such a box is open asks to quit instead.
- **Commands:** `make delete_run RUN=folder`, `make trash`, `make restore TRASH=entry`, `make empty_trash`, and the Commands tab's new **Files** group (Delete a run, Trash, Restore from the trash, Empty the trash). The Runs tab has a Delete run button, right-aligned and apart from the others, disabled for a live run.
- In a terminal, `make empty_trash` doesn't ask: typing it is the confirmation.

## Consequences

- Deleting an agent (6c) adds kind "agent" entries that also move its runs, with the rules in the roadmap's step 6.
- The trash grows until you empty it.
