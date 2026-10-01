# 060: A stopped agent must press gas or reverse

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7f6 (`mask_stopped` in `src/agents/network.py`, the dataset filter in `src/experiments/datasets.py`).

## Context

Agents got stuck repeating "non-moving" controls: steering, braking, or nothing while stopped. In this game a stopped car can't turn (steering needs speed), and brake or no pedal keeps it at 0, so those choices are sitting still, paying the stopped cost (-30/s) round after round. The first idea was to require gas or reverse in every control ("W and space" to slow down), but brake already beats gas in the game, so W + space is exactly space: that rule would change keys, not driving. Shrinking the agent to 6 actions (gas or reverse only) would lose coasting and gentle braking, and the heuristic brakes and coasts, so a clone couldn't copy it and the heuristic (the bar every skill is measured against) would have to change.

## Decision

- **Only while the car is stopped** (its speed input is exactly 0), the agent can't pick an action whose pedal is none or brake: it must press gas or reverse (6 of the 12 actions, any steering). Moving, all 12 stay, so braking and coasting work as before.
- **In the network itself:** `PolicyNetwork.forward` gives the blocked actions a score of -1e9, so their probability is 0 everywhere the policy is used (training's sampling, PPO's update, the agent driver, the evaluation, the showcase). PPO re-scores its past choices with the same rule, so its ratios stay right; -1e9 (not minus infinity) keeps the entropy finite.
- **Datasets leave sitting still out:** a recorded decision taken while stopped with neither gas nor reverse is dropped (as the idle wait before the first key already was): it's the habit we don't want, and the policy can't output it. The heuristic never sits still, so its dataset is unchanged (50 rounds, about 166,000 samples, none skipped).
- **The game doesn't change:** the physics, keyboard driving, the heuristic, replays, and scores are the same. Only an agent's choices are restricted, so agents trained before start over (none existed).

## Consequences

- A car pinned against a wall with gas pressed is stopped too; reverse is always among its choices, the way out.
- Dropping still decisions shortens a recording's reward sequence slightly for the value head's targets: a small approximation.
