# 080: What RL does after cloning, and anchoring it to the clone

**Date:** 2026-10-05. **Status:** Accepted (an investigation; the anchor is a trainer option, off by default). The `anchor` key in trainer files (`src/agents/trainer.py`, `src/agents/ppo.py`, `src/experiments/training.py`).

## Context

agent_2 (the navigator's clone, then `finetune` up the `skills` curriculum with 4 games) went full speed into walls: 10 of 20 arena rounds ended in a wreck. agent_3 and agent_4 before it showed the same pattern: RL never got much past the clone, and got faster and crashier.

## What was measured

A scorecard less noisy than the suite: each skill over 20 rounds on fresh seeds (the suite plays 5), and 20 arena rounds. All experiments in a scratch folder, from the same clone (agent_1@clone-e100), 2M decisions, 4 games.

| Run | Average share | Suite wrecks | Survival | Arena wrecks | Arena fuels |
|---|---|---|---|---|---|
| The clone | 1.54 | 0.08 | 0.97 | 0.10 | 24.9 |
| agent_2: `finetune`, discount 0.99 | 1.53 | 0.41 | 0.82 | 0.85 | 14.2 |
| A: discount 0.995 | 1.48 | 0.26 | 0.86 | 0.80 | 11.3 |
| B: a navigator that brakes for walls near fuel, cloned (no RL) | 1.04 | 0.20 | 0.90 | 0.20 | 19.6 |
| D: discount 0.995, anchor 0.3 | 1.51 | 0.24 | 0.87 | 0.20 | 21.4 |
| D: discount 0.995, anchor 1.0 (at 1M) | 1.38 | 0.26 | 0.95 | 0.05 | 23.1 |

- **How it wrecks:** hard hits, not scraping (1,292 health lost to hits, 62 to scraping, in 20 arena rounds). 6 of 10 wrecks came within 1.7 s of taking a fuel at near full speed, the next fuel 53 to 177 degrees off: a turn at full speed into a wall. Arena fuels sit 40 px from walls; stopping from full speed takes 75 px.
- **Not the reward:** in agent_2's training, arena rounds that survived earned 23,573, wrecked ones 7,105, at the same pace (0.47 against 0.45 fuels a second). Wrecks are mistakes it doesn't learn to avoid, not a trade it chooses.
- **A cost for keeping the stopping distance** (wall ahead closer than the stopping distance) wasn't tried in training: the safe clone ran into it more than agent_2 (39,066 against 29,810 px-steps a round with a 90-degree view), because the wrecks come from turning into side walls.
- **Fuels 100 px from walls** would hide the trap rather than teach the skill: braking before a fuel near a wall is driving skill, for humans and agents alike, so the maps stay.

## Decision

- **A trainer option, `anchor`** (0 = off, the default; not written to the file when off): the PPO loss adds this times the KL divergence from the phase's starting checkpoint's choices to the policy's, on the rollout's situations, so RL keeps a good start's habits and departs where that clearly pays. `learning.csv` gets an `anchor_kl` column. The starting checkpoint is the phase's own (a branch's "initial" is the clone).
- **No RL variant beat the clone.** The anchor stops the drift into recklessness (arena wrecks 85 % to 5 to 25 %), but adds no skill; RL raises its reward on the training maps without carrying it to the test maps. The best driver today is the clone.

## Consequences

- Trainer files are unchanged; `anchor` is there for experiments and later trainers.
- Next to try (not measured): cloning more and better, since cloning is what works: the navigator labelling the clone's own situations (DAgger with an automatic expert), so the clone learns where its mistakes start.
