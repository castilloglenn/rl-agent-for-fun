# 064: Taking over while watching (testing only)

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7f9 (`MazeCarDemo` in `src/envs/maze_car/demo.py`).

## Context

Watching an agent from early in its training, you wanted to nudge it out of a stuck spot and see how it carries on, without that touching its training.

## Decision

- **In the watch window** (watching any driver that isn't you: an agent, or the heuristic), **holding a driving key** (W A S D, the arrows, Space) drives the car with your keys; **letting go** hands it back at once. The driver keeps deciding every step all along, so an agent's MIND card shows what it would do while you drive, and it carries on from where you left the car.
- **You see it:** the DRIVER card says "YOU are driving" (amber) while a key is held, then "Live play · you took over 3x (4 s)" for this round (a new round clears it). The shortcuts box lists the keys.
- **Testing only:** watching records nothing (no replay, no recording), so your driving never reaches a dataset or a training, and the agent learns nothing from it. The showcase keeps its own keys (Left, Right, Space) and replays the evaluation's exact rounds, so it has no take-over.

## Consequences

- Teaching the agent from your corrections (expert labelling, roadmap 7g) is a separate, opt-in step: it would record your take-overs as data.
