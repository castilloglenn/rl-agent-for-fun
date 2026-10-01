# 057: A wall contact counts for the reward only after a real gap

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7f1 (`_contact` and `StepEvents.clear_seconds` in `src/envs/maze_car/rewards.py`, `_clear_seconds` in `src/envs/maze_car/env.py`, `rewards/default.json`).

## Context

agent_2 started as a clone of the heuristic (share 1.27), stayed near it until about 1M decisions, then collapsed to 0.27, coasting half the time. Playing its checkpoints on the training maps, with each reward term summed, showed why: the contact cost of one 120 s round reached -15,400 (d0400k on the box) and -19,600 (d2000k on course_small). The game counts a new contact whenever the car wasn't touching a wall the step before (that's its rule for damage), so a car wiggling against a wall starts a new one every few steps: 150 to 200 a round, each -100, even with no damage. Against that, a checkpoint is +500 and standing still costs at most -3,600 a round, so doing little became the safest policy.

## Decision

- **The `contact` term counts a new contact only after the car was clear of walls for `clear` seconds** (a new term parameter, default 0.5 s, written in `rewards/default.json`). The env passes each step the seconds since the car last touched a wall (`clear_seconds`, inf before its first touch).
- **Only the reward changes:** the game's contacts, damage, health, scores, and replays stay as they were.
- Measured: rocking against a wall every 6 to 30 steps for 20 s makes 36 to 67 game contacts, and now 1 reward contact (-100, not up to -6,700). Backing off 0.75 s between hits still counts each hit.

## Consequences

- Agents trained before this learned from the harsher count; all were deleted for a clean start.
- Next (7f2): `course_small` gives no checkpoints even to the heuristic, so a quarter of `skill_training`'s rounds only ever cost reward.
