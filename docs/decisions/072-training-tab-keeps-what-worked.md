# 072: The Training tab keeps to what worked

**Date:** 2026-10-02. **Status:** Accepted. Built in roadmap 7f17 (`src/control/training_tab.py`).

## Context

The latest agent, agent_3, learned the game's basic controls by cloning the navigator and then training with the `finetune` trainer up the `skills` curriculum. The `default` trainer let agent_2's choices drift apart (decision 070), and training on one stage or mix by hand was replaced by the curriculum (decision 063). New features come next, and the form offered every trainer, stage, and mix.

## Decision

- **Trainer:** every RL trainer except `default`; `finetune` by default.
- **Stage:** curricula only; `skills` by default.
- **Only the Training tab.** The Commands tab and the make targets still offer every trainer, stage, and mix, and the files stay.

## Consequences

- Training a fresh agent from the tab uses `finetune` too (a third of the default learning rate): to train one with `default`, use the Commands tab or `make train`.
