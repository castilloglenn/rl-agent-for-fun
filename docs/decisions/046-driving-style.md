# 046: Driving style, measured while scoring

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7c9 (`src/utils/driving_style.py`, `evaluation.py`, the Agents and Runs tabs, `make agent`).

## Context

agent-1, trained on the box with the new default reward (7e), drove backward 91 to 100 % of the time at every checkpoint (measured on the suite's Open field rounds, 2026-09-30), and its scores alone didn't say so. That finding changed the reward (progress while reversing now pays nothing, decision 041).

## Decision

- **Counted while scoring, no extra games:** every step of the suite's rounds (not the braking starts, which are all braking by design) counts its pedal (forward, brake, coast, or reverse, in the game's order: brake beats gas, gas beats reverse), its turning (left, right, or straight), and whether the car actually moved backward. Each checkpoint's row and its `scored` event get `style_forward`, `style_brake`, `style_coast`, `style_reverse` (they add up to 1), `style_left`, `style_right`, and `style_backward`; the heuristic's baseline gets them too, as a reference.
- **Warnings when one habit dominates:** moving backward over 40 % of the time, braking over 50 %, coasting over 70 %, turning one way over 80 % ("circles").
- **Where it shows:** the Agents tab profile's DRIVING line (amber with a warning), its history chart (forward, reversing, backward over the checkpoints), the leaderboard's new share column (the ranking since 7d3b), the Runs tab's "Driving style" chart (a line per pedal over the run's scored checkpoints), and `make agent`.
- **The suite moves to skills-v2,** so every checkpoint is scored again with its style: no fallback for rows without it.

## Consequences

- Every agent needs `make eval AGENT=<id>` once (about 5 s a checkpoint).
- Fixed on the way: the Agents tab's milestone line read `heuristic_score`, which skills milestones don't have (it would have crashed on the first one); the agent cards showed the share as the big number, rounded to 0 (now the game score, with the share beside it).
- The tests turn off sound (`tests/conftest.py`, `SDL_AUDIODRIVER=dummy`): on 2026-10-01 macOS's audio failed (CoreAudio error -66681) and `pygame.init()` stalled about 23 s each time, so the test run hung.
