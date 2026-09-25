# 011: Reward profiles: agent rewards as weighted terms in files

**Date:** 2026-09-25. **Status:** Implemented in roadmap step 4c (`src/envs/maze_car/rewards.py`, `rewards/default.json`). Recording profiles in replays and runs follows in 4d and 4h.

## Context

The reward is the only thing an agent optimizes, so its weights shape the behavior it learns (reward shaping). Step 4a separated the agent reward from the game score, but only one reward function exists (`points_gained`), and it's picked by name in code. Reward experiments are a core part of the project, and every run should record exactly which reward trained an agent.

## Decision

The agent reward is a **weighted sum of terms**, defined in a **profile file**, like stages:

```json
{
  "format": 1,
  "name": "cautious",
  "description": "Stay alive: crashing costs far more than points earn.",
  "terms": {"points": 1.0, "crash": -200, "per_step": -0.01}
}
```

- `description` is optional, in plain words: what the profile is for. It'll show on agent profile pages.
- Profiles live in `rewards/<name>.json`. `rewards/default.json` is `{"points": 1.0}`, exactly today's reward.
- **reward = Σ weight × term.** Each term is one number measured over a single step:

  | Term | Value per step |
  |---|---|
  | `points` | Game points gained |
  | `checkpoints` | Checkpoints reached |
  | `crash` | 1 on the step the car goes out |
  | `time_up` | 1 on the step the round ends on time |
  | `per_step` | 1 every step (a time cost or bonus) |
  | `distance` | px moved forward |
  | `speed` | Speed as a fraction of max speed |
  | `steering_change` | How much the steering wheel moved |
  | `closest_wall` | Shortest ray distance, as a fraction of the field diagonal |

- Unknown term names or a wrong `format` fail early with a clear error. New terms can be added later, and old profiles keep working.
- The env takes a profile by name or path. The profile's **full content** is recorded in replays and run configs, so an edited or deleted profile file doesn't lose the record.

### Examples (ideas for experiments, not shipped)

| Profile | Terms | Likely behavior |
|---|---|---|
| cautious | points, big crash penalty | Slower, keeps away from walls |
| hunter | checkpoints ×300, distance ×0.02 | Beelines to checkpoints, takes risks |
| smooth | points, small steering-change penalty | Fewer zigzags |
| urgent | points, small per-step penalty | Rushes |

## Consequences

- **The game score is never affected.** Agents trained with different profiles still compete on the same leaderboard.
- Agents can exploit weights in unexpected ways. A crash penalty that's too large can teach "never move", the classic loophole. Replays make such behavior visible.
- The agent profile page (step 6) shows which reward profile trained the agent, next to its skills.
- **Shown in the window:** the top bar has `REWARD <profile name>`, and the side panel's AGENT REWARD section shows the last step's reward and the total this game. The reward is computed in the human demo too, so you can see how a profile would judge your own driving. The panel's SCORE section keeps showing game points.
