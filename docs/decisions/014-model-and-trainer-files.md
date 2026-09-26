# 014: Agent models and training profiles as files

**Date:** 2026-09-26. **Status:** Accepted. Model files implemented in roadmap step 5a1 (`src/agents/`, `models/small.json`, `models/medium.json`, `make new_agent`). Trainer files implemented in 5a2 (`src/agents/trainer.py`, `trainers/default.json`, `make train`). Evaluation intervals moved to 5a5, with the evaluation suite.

## Context

An agent has settings worth tweaking, from the command line now and the control center later. They come in two kinds: some define the network itself, and can't change once it has learned weights; others only affect how it learns, and can change between training phases.

## Decision

Two new file types, like stages, rules, and reward profiles:

### Models: `models/<name>.json`, fixed for an agent's life

```json
{
  "format": 1,
  "name": "small",
  "description": "Two layers of 64: small, fast, enough for the box stage.",
  "hidden": [64, 64],
  "activation": "tanh",
  "observation_version": 1,
  "actions": "canonical12",
  "action_repeat": 4
}
```

| Setting | Changes |
|---|---|
| `hidden`, `activation` | Network size and shape: how much the agent can learn |
| `observation_version` | What it perceives (later: an observation spec with ray counts, compass on or off) |
| `actions` | What it can do (the 12 canonical actions, [decision 012](012-agent-training-modes.md)) |
| `action_repeat` | How often it decides (4 = 30 decisions/s, [decision 008](008-fixed-timestep-clock.md)) |

- Picked when an agent is created, and **copied into the agent**: the agent owns its model.
- **Safety rule:** resuming or loading an agent with a different model is refused, because the weights wouldn't fit. Create a new agent, or imitate the old one (5b).

### Trainers: `trainers/<name>.json`, changeable per training phase

`trainers/default.json`:

| Key | Default | Means |
|---|---|---|
| `algorithm` | `ppo` | Only PPO (Proximal Policy Optimization) for now |
| `learning_rate` | 0.0003 | Step size of each update |
| `gamma` | 0.99 | Discount: how far ahead the agent cares (about 100 decisions, 3 s) |
| `gae_lambda` | 0.95 | Smoothing of the advantage estimate (GAE: Generalized Advantage Estimation) |
| `clip` | 0.2 | How far one update may move the policy |
| `entropy` | 0.01 | Exploration bonus |
| `value_coef`, `max_grad_norm` | 0.5, 0.5 | Standard PPO stability terms |
| `reward_scale` | 0.01 | The learner sees rewards times this (added in 5a4; measured: at 1.5M decisions, mean score 5,234 and 100 % survival with 0.01, against 3,907 and 90 % with 1). The same factor on every reward doesn't change the best driving, but keeps the value head's error (rewards in the hundreds) from using up the shared gradient limit. Metrics and the HUD show real rewards |
| `rollout` | 2048 | Decisions collected per update |
| `minibatch`, `epochs` | 64, 10 | How each rollout is learned from |
| `total_decisions` | 2,000,000 | Length of the training phase (1M until 5a4: with sliding walls, learning starts later) |
| `checkpoint_every` | 100,000 | Decisions between saved weights |
| `seed` | 0 | Action sampling and minibatch order |

Unknown or missing keys are refused, so a typo can't silently fall back to a default.

- Picked per training phase. The agent's lineage records every phase's trainer, next to its reward profile, stage, and rules.

## Consequences

- A training run = model (new agent only) + trainer + stage + rules + reward profile. The control center (step 6) lists and picks each.
- The agent profile page shows its model, and each phase's trainer and reward profile.
