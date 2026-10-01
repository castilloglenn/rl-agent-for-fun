# 056: Reward by term over training

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 6e (`EpisodeResult.terms`, `metrics_columns` in `src/experiments/runner.py`, the "Reward by term" chart in `src/control/runs.py`).

## Context

`metrics.csv` kept one agent reward per episode, the sum of the reward profile's terms (progress, checkpoints, contact, damage, wrecked, stopped). A rising total doesn't say whether the agent drives better, avoids walls better, or found a loophole: agent-1's backward driving was found later, from its driving style. The game window's AGENT card (decision 032) shows the split live, but nothing kept it.

## Decision

- **Each episode keeps each term's weighted sum** (`EpisodeResult.terms`, from the env's `round_terms`), and `metrics.csv` gets a column per term of the run's reward profile, `reward:<term>`, in the profile's order, for training and episode runs alike. The columns add up to the `reward` column.
- **"Reward by term"** in the Runs tab's lower chart (training and episode runs): a line per term, the mean of its last 20 episodes, gains above 0 and costs below, in fixed colors (progress green, checkpoints blue, contact amber, damage orange, wrecked red, stopped gray). Training plots it by decisions (each episode's steps over the action repeat, added up), episode runs by episode. The legend wraps to two rows, and resting on a term explains it (the reward profiles' help).
- **No compare on this chart:** six more muted lines would be unreadable.

## Consequences

- Runs from before this have no term columns: the chart says "No data yet" (no backfill, first version).
- A mixed run's lines mix its maps, like its training score.
