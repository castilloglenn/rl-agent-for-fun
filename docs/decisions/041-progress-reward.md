# 041: Progress along the path, and a new default reward

**Date:** 2026-09-30. **Status:** Accepted. Built in roadmap 7e (moved up): `src/sim/paths.py`, the `progress` term in `src/envs/maze_car/rewards.py`, and `rewards/default.json`.

## Context

The default reward was the game score (+1 per 10 px driven forward, +100 per checkpoint) minus wall costs. At full speed, driving paid about 30 per second, more than the agents' checkpoints did (about 12.5 a minute), and it paid in any direction: circling at full speed was rewarded. A "full speed pays 1, anything else 0.5" rule was considered and turned down: crawling would pay half the maximum, speed would pay whatever the direction, and slowing for a turn would halve the reward.

## Decision

- **A progress term:** px closer to the checkpoint this step, along a drivable path around the walls (`PathField`: a 10 px grid, walls and the border grown by half the car's width so a gap narrower than the car is closed, Dijkstra over 8 neighbors without cutting corners, blended between cells so it never jumps; with no walls, the straight line). Farther counts negative. Reaching a checkpoint doesn't count the next one's distance: progress always compares the same checkpoint before and after a step.
- **It can't be farmed:** it's a difference of one distance (potential-based shaping), so any loop nets zero. Gains while reversing count half (`"reverse": 0.5`), losses always in full, so no back-and-forth can gain either.
- **The agent never sees the path.** Its observation is unchanged (rays, speed, steering, the straight-line compass, time, health). The path only grades its actions in training, and game points (the score, leaderboards, suites) don't know about it.
- **`rewards/default.json` changes** (not a new profile: the default is still being built): progress +0.1 per px, **+500 per checkpoint**, -100 per wall contact however light, -1000 per full loss of health on top (a 25 % hit: -350 with the contact), **-3000 for a wreck**, -0.25 per step stopped. Game points are no longer part of the reward. So: bump < hit < big hit < wreck, and a checkpoint is worth more than a medium hit.
- **Exploration stays as is** (the trainer's entropy bonus, 0.01): agents end training at an entropy around 1.2 to 1.35 (fully random: 2.48), and the progress term rewards going around walls directly. Raise it only if the Entropy chart collapses early.

## Consequences

- Old runs, replays, and agent phases keep the profile they were made with (each stores its copy), so they resume and verify as before; "reward: default" in an old phase means the old one.
- The path is only computed for a profile that uses `progress`: about 9 % slower steps on the box, 12 % on the arena (measured 2026-09-30, heuristic driver), and a path field per new checkpoint (about 3 ms on a box-sized stage with walls, 10 ms on the arena).
- To see if it works: train an agent on the new default and compare it with one trained on the old (its runs and the suite).
