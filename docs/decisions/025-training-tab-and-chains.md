# 025: The Training tab: one form, run as a chain of existing actions

**Date:** 2026-09-27. **Status:** Accepted. Implemented in roadmap step 6b2 (`src/control/training_tab.py`, `training_plan.py`, `chains.py`, `form.py`).

## Context

Training an agent took up to three commands in the right order: create it (or branch it), clone your driving, then train it with RL. The Commands tab has each one as an action, but you had to know the order and fill in the same agent three times. Step 6b2 is one form for all of it.

## Decision

- **Three modes:** RL, Imitation, and Imitation then RL. The agent is an existing one or "(new agent)", which asks for a name and a start: fresh from a model, or branched from any agent's checkpoint. Only the fields a mode uses show, and the form rebuilds (keeping your values) when Mode, Agent, or Start changes.
- **A plan, not a new command:** the form turns into steps, each one a Commands tab action (Create an agent, Clone your driving, Train). The plan box shows each step in plain words, and the terminal equivalent (`python app.py … && python app.py …`). So there are no new flags or make targets.
- **Chains** (`chains.py`) run the steps one after another as ordinary jobs, labeled with their place (`Train: rookie2 (2/2)`). The next step starts only if the previous one exited with code 0. Stopping a step, or a step failing, cancels the rest, and the job's console says so.
- **An estimate from your own runs:** the pace (seconds per decision, or per epoch for imitation) of your last 3 finished runs of the same kind, times the trainer file's total. Without a past run of a kind it says "no estimate" rather than half a number.
- **What blocks Start** (the button greys out, and the reason shows in red): no name, a name with other than letters, digits, `-` and `_`, a name that exists, a seed or round seconds that isn't a number, an agent being trained right now (a live run of it, or a chain here working on it), and a dataset with no recordings yet. Being on battery is a warning only (amber).
- **Start opens the Runs tab** and has it follow the chain: it selects each run the chain starts (the imitation run, then the training run), until you pick another run yourself.
- **The form** (`form.py`) is a reusable column of fields with the Commands tab's look: labels, dropdowns from the files on disk, dimmed hints, and scrolling by hand.
- Checking a dataset's usable rounds means re-simulating its recordings (about 3 s), too slow for a live form. The form only counts its recordings; the imitation step itself reports unusable ones.

## Consequences

- Changing a trainer's total decisions still means another trainer file (6d edits them).
- A chain lives in the control center: quitting it stops the running step, and the rest never start.
- The Commands tab keeps its own field code; it could move onto `Form` later.
