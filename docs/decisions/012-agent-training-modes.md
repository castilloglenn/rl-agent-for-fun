# 012: Agents can learn by imitation, by RL, or both, in any order

**Date:** 2026-09-25. **Status:** Accepted. Implemented so far: the player in driver records (4d), the driver interface and the 12 canonical actions in code (4f, `src/drivers/`), with a test that all 32 key combinations behave like their canonical action. Per-player recordings with kept runs (4i, `src/replay/recordings.py`). The agent driver, `agent:<id>` in the registry, with the record `{"type": "agent", "id", "checkpoint"}` (5a1, `src/agents/`). PPO training phases (5a2, `make train`). Planned: 5a3 onward, 5b. Baseline drivers use the record `{"type": "baseline", "id": ...}`.

## Context

The owner wants to build an agent from their own recorded runs (imitation learning, specifically behavioral cloning), and keep the option to improve it further with RL. Training modes should stay flexible: imitation only, RL only, or both.

## Decision

### Training modes

An agent's training is a sequence of **phases**, recorded in its lineage:

| Mode | Phases | Use |
|---|---|---|
| Imitation only | imitation (player's runs) | A pure clone of a player |
| RL only | RL (reward profile) | Learn from scratch |
| Imitation, then RL | imitation → RL | Start from a player's style, then improve beyond it |
| RL, then imitation | RL → imitation | Nudge an RL agent toward a player's style |

Any checkpoint can be **branched** into a new mode. The agent profile page lists every phase, for example "cloned from zen (20 runs), then RL with cautious for 1M steps".

### Groundwork (in steps already planned)

| Where | Groundwork |
|---|---|
| 4d replay format | The human driver record includes the **player**: `{"type": "human", "player": "zen", "device": "keyboard"}` |
| 4f baseline drivers | **One driver interface** (observation in, action out) for every driver: random, heuristic, RL, imitation |
| 4i demo recordings | Stored **per player**, and runs can be **kept** (never removed by the latest-50 limit) |
| 5a RL agent | The action set covers every human input, and the network shape works for both modes (below) |

### The action set loses nothing from human input

The simulation already resolves input priorities: left + right cancel, and brake beats gas beats reverse. So every one of the 32 combinations of the 5 keys behaves exactly like one of **12 canonical actions**:

- Steering: left, none, right (3)
- Pedal: none, gas, reverse, brake (4)

A 12-action discrete set therefore represents any human run exactly, and it's small enough for learning.

### One network for both modes (algorithm note for 5a)

Imitation trains a network to output **action probabilities** from an observation. Policy-based RL algorithms such as **PPO** (Proximal Policy Optimization) use exactly that kind of network, so a clone's weights can start an RL run directly. Value-based DQN (Deep Q-Network) outputs action values instead, which don't come from imitation training without extra steps. Recommendation for 5a: **PPO**, to keep imitation → RL simple. The final choice is made when planning 5a.

## Consequences

- An imitation dataset needs no extra recording format: replays re-simulate to (observation, action) pairs at any time, with the current observation layout.
- If the simulation changes, old replays are flagged as out of date (decision 003), so a dataset never silently trains on wrong observations.
- Clones copy their player's mistakes and can drift into unrecorded situations. More varied runs and RL fine-tuning counter this.
