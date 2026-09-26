# 014: Agent models and training profiles as files

**Date:** 2026-09-26. **Status:** Accepted. Model files implemented in roadmap step 5a1 (`src/agents/`, `models/small.json`, `models/medium.json`, `make new_agent`). Trainer files: planned for 5a2.

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

Learning rate, discount (gamma: how far ahead the agent cares), exploration bonus (entropy), rollout and batch sizes, update epochs, total steps, checkpoint and evaluation intervals, and seeds. Defined in detail in 5a2.

- Picked per training phase. The agent's lineage records every phase's trainer, next to its reward profile, stage, and rules.

## Consequences

- A training run = model (new agent only) + trainer + stage + rules + reward profile. The control center (step 6) lists and picks each.
- The agent profile page shows its model, and each phase's trainer and reward profile.
