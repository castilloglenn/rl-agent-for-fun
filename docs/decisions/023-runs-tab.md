# 023: The Runs tab: every run, read from its files, with live curves

**Date:** 2026-09-27. **Status:** Accepted. Implemented in roadmap step 6b1 (`src/control/runs.py`, `charts.py`, `runs_tab.py`).

## Context

Step 6b brings training and runs into the control center. Runs already write everything to their folders (`config.json`, `learning.csv`, `metrics.csv`, `summary.json`, and the agent's `history.jsonl`), and the control center has no messaging layer ([decision 022](022-control-center-in-pygame.md)). 6b is split into three sub-steps: 6b1, the Runs tab (this decision); 6b2, a training form; 6b3, branching and comparing from the charts.

## Decision

- **A Runs tab, full height:** the run list on the left, the selected run on the right. The console and jobs box stay on the Commands tab, so the charts get about 680 px instead of 390.
- **Every run kind:** training, imitation, and episode runs, newest first. A row shows when it started (from the folder name), kind, agent or driver, and a short status (its percentage while running).
- **Status from the files, no reporting:**

  | Status | When |
  |---|---|
  | running, paused | One of our jobs is running it |
  | running elsewhere | A training's `training.lock` names a live process (for example `make train` in a terminal), or another run's CSV files changed in the last 30 s |
  | stopped | Its summary says interrupted (Ctrl+C). A training with `resume.pt` can be resumed |
  | done | Its summary says it finished |
  | ended unexpectedly | No summary, and nothing running: it crashed or was killed. A training with `resume.pt` can still be resumed |

  Training uses the lock rather than file times, so a training paused from a terminal (Ctrl+Z) still counts as running.
- **Linking a job to its run:** training, resume, imitation, and episode runs print `Run: <folder>` as soon as the folder exists (an `on_start` callback in each, printed by `app.py`). The job remembers it. A training is also linked by the process id in its lock.
- **Live, cheaply:** every second, the tab rescans the folders (configs are read once) and reads only the lines a CSV file has gained since the last read. A file that shrank (Ctrl+C trims the rows after the last update) is read again from the start.
- **Charts, drawn by hand** (`charts.py`, in the game window's style): lines, dots, a ring, and a dashed level. Hovering reads out the nearest point of each series; the legend shows the latest values otherwise, with exact numbers where the axes round.

  | Run | Chart 1 | Chart 2 (a dropdown) |
  |---|---|---|
  | Training | Score: the training score (mean of the last 20 episodes), the suite score at each checkpoint this run saved (from the agent's history), the best checkpoint ringed, the heuristic's suite score dashed | Agent reward, entropy, policy loss, value loss, KL divergence, clip fraction |
  | Imitation | Accuracy on the training rounds and the held-out rounds, per epoch | Loss (train and held-out), value loss |
  | Episodes | Score per episode, and its mean over 20 | Agent reward, checkpoints, distance points, steps |

  Training's x-axis is the agent's total decisions, so a branched agent's curve lines up with its suite scores.
- **The header:** the run's name, its settings (agent and start, trainer, stage, rules, reward, seed), the status with a progress bar, done / total, the time left (from the pace of the last 20 rows) or how long it took, and the key result (for example "suite best d1700k 5,347").
- **Buttons start the Commands tab's actions** (Resume training, Watch a run's best replay) or control the run's job (Stop, Pause, Resume), so the tab adds no commands of its own. Each is enabled only when it applies.

## Consequences

- The Runs tab reads the runs you start anywhere: from the control center, or `make train` in a terminal.
- A run from before this change has no `Run:` line; it still lists, only unlinked from a job.
- 6b2 (the training form) can switch to the Runs tab with its new run selected. 6b3 can hang branching and comparing on the charts' checkpoint dots.
