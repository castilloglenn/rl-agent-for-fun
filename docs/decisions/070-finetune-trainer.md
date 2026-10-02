# 070: A gentler trainer for continuing a clone

**Date:** 2026-10-02. **Status:** Accepted. Built in roadmap 7f13 (`trainers/finetune.json`, `make finetune AGENT=id`).

## Context

agent_2, branched from the navigator's clone (share 1.59) and trained with the default trainer on the `skills` curriculum, reached level 2 by its goal at 272k decisions and peaked at share 2.13 (d0300k), then slid back to about 1.1 to 1.3 by 2M. In its own training rounds it got worse on every map in the last quarter (box 24.5 to 20.2 checkpoints a minute, `course_large` 21.0 to 15.5, `course_small` 13.2 to 4.9), its wreck rate rose from 0.07 to 0.3, and coasting rose from 13 % to 30 %. Its entropy (how random its choices are) went from 0.23, the clone's sharp policy, to 0.81. The default trainer is made for learning from scratch: a learning rate of 0.0003 and an entropy bonus of 0.01 that pays the policy for being more random. For a skilled clone that blurs what it knows faster than RL improves it (likely, from the entropy; a run with this trainer tests it).

## Decision

- **`finetune`**, a PPO trainer for continuing a clone: the default's settings with a learning rate of 0.0001 (a third) and an entropy bonus of 0.001 (a tenth), 2M decisions.
- `make finetune AGENT=id` trains it on the `skills` curriculum with it; the Training tab's Trainer list has it too.
- If a clone still drifts with it, the next step is a penalty for moving away from the clone's own choices, fading over training.

## Consequences

- agent_2 stays, to compare with: same clone, same curriculum, default trainer.
