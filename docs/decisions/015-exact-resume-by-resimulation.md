# 015: Exact resume by re-simulation, and branching as new agents

**Date:** 2026-09-26. **Status:** Implemented in roadmap step 5a3 (`src/experiments/training.py`, `src/agents/store.py`, `make resume`, `make resume_last`).

## Context

A stopped training run should continue as if it had never stopped: same weights, same learning curve, same episodes. Weights alone aren't enough. The optimizer's memory, the random state for sampling and minibatch order, and the game in progress all shape what comes next. The game in progress is a whole ECS world, which has no save format.

## Decision

- **A resume state per run:** `runs/<run>/resume.pt`, rewritten (never half-written) after every update. It holds the weights, optimizer state, torch random state, counters (decisions, updates, episodes, best score, checkpoints written), each finished episode's result, and **the current episode's seed plus its decisions so far**.
- **The game is rebuilt by re-simulation:** reset with the episode's seed, then play its decisions again. The simulation is deterministic (the same guarantee replays rely on, [decision 003](003-replay-over-multi-window.md)), so this reproduces the exact state without a world save format. It costs at most one round (7,200 steps, about 0.2 s).
- **Ctrl+C goes back to the last update.** Ctrl+C can land mid-rollout or mid-update. The run rolls back to the last resume state, trims `metrics.csv` and `learning.csv` to it, and keeps its weights as a checkpoint. Resuming replays the dropped decisions identically.
- **Checkpoints know their run.** Each checkpoint records the run that wrote it. A resume redoing an update rewrites that run's own checkpoint, and never overwrites another run's.
- **Safety:** resume is refused if another run trained the agent since, or if the run is still training (a `training.lock` with a live process id), already finished, or has no resume state.
- **Branch = a new agent:** `python app.py -new_agent <id> --from <agent>@<checkpoint>` copies the model and that checkpoint into a new agent as its `initial`, recording `branched_from` and keeping the decision count going. Training an old checkpoint in place would give one agent two histories.
- **Pause in place moves to step 6.** Keeping training in memory while watching replays or live play needs a window to pause from. In the terminal, Ctrl+C plus exact resume covers it.

## Consequences

- A test stops a run at an update, mid-update, and twice, and checks that the resumed run matches an uninterrupted one exactly: weights, `learning.csv` (all but its seconds column), `metrics.csv`, and replay names. It fails if the random state, optimizer state, or episode re-simulation is left out.
- Resume depends on the simulation staying deterministic, like replays. If the code changes between stop and resume, the rebuilt episode can differ.
- Runs trained before 5a3 have no resume state and can't be resumed. Their weights still train further with `make train`.
