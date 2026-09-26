# 019: Imitation agents from your recordings

**Date:** 2026-09-27. **Status:** Implemented in roadmap step 5b (`src/experiments/datasets.py`, `src/experiments/imitation.py`, `datasets/mine.json`, `trainers/imitate.json`, `make dataset`, `make imitate`).

## Context

Decision 012 planned agents that learn from a player's recorded runs (behavioral cloning), then optionally keep improving with RL. Recordings store only actions, and agents decide every 4 steps while a player can change keys every step.

## Decision

- **A dataset is a file**, `datasets/<name>.json`: the player, `all` or `kept` recordings, and a `min_score`.
- **Samples by re-simulation:** each recording is replayed (deterministic) to rebuild its observations. Recordings that don't verify (older physics) or have another observation version are skipped, with the reason shown.
- **Labels:** one sample per agent decision (every 4 steps): the observation at the decision step, labeled with the player's most-pressed action over those 4 steps.
- **The idle wait before the first key is left out.** It's reaction time, not driving, and it taught clones that a stopped car should stay stopped (84 % of stopped samples were "press nothing", and the first clone never moved).
- **Held-out check by whole rounds,** not single samples, so near-copies of training samples can't flatter the accuracy.
- **An imitation trainer file** (`algorithm: imitation`): learning rate, 100 epochs, minibatch, held-out share, seed, and `value: true`, which also fits the value head to the rounds' discounted rewards (with the RL trainer's gamma and reward scale), so an RL phase starts smoothly. Imitation and RL trainer files can't be mixed up.
- **The clone is a checkpoint** (`clone-e100`) of an agent, new or existing, recorded in its history as an `imitation` phase. `make train` then continues it with RL.

## Consequences

Measured on the box suite (heuristic: 2,574):

| Clone of | Data | Held-out accuracy | Suite score |
|---|---|---|---|
| The heuristic, 30 epochs | 20 rounds | 71 % | 500 |
| **The heuristic, 100 epochs** | 20 rounds | 76 % | **1,319** |
| The heuristic, 300 epochs | 20 rounds | 79 % | 1,136 |
| Your recordings, all | 8 rounds (5 short or aborted) | 59 % | 5 |
| Your recordings, score ≥ 1,000 | 3 rounds | 39 % | 1,169 |

- **A clone reaches about half its teacher.** Small errors compound into situations the teacher never showed.
- **Data quality matters most:** short or aborted rounds ruin a clone. Set `min_score`, or keep (K) only good rounds and use `include: kept`.
- **RL from a clone gets a real headstart.** From the heuristic clone, RL reached 3,802 at 100k decisions and 4,644 at 500k, where from scratch it had 5 and 2,312 (rookie reached about 4,600 only around 1M).
