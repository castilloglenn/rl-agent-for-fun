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
  "description": "Stay alive: a wreck costs far more than points earn.",
  "terms": {"points": 1.0, "wrecked": -200, "per_step": -0.01}
}
```

- `description` is optional, in plain words: what the profile is for. It'll show on agent profile pages.
- Profiles live in `rewards/<name>.json`. `rewards/default.json` was `{"points": 1.0}`, exactly the reward before profiles. After 5a2 it added a crash penalty, and since 5a4 (car health) it is `{"points": 1.0, "damage": -500, "contact": -100, "stopped": -0.25}` (see Consequences).
- **reward = Σ weight × term.** Each term is one number measured over a single step:

  | Term | Value per step |
  |---|---|
  | `points` | Game points gained: distance **and** checkpoints |
  | `distance_points` | Game points from driving only, without checkpoints. Pair it with `checkpoint_speed` when a checkpoint's worth should come only from how fast it's reached |
  | `checkpoints` | Checkpoints reached |
  | `checkpoint_speed` | Per checkpoint reached: `max(0, 1 - seconds on the field / window)`, so 1 for an instant pickup down to 0 at `window` (default 10 s). Added after 4c |
  | `damage` | Share of full health lost this step (0 to 1). Added in 5a4 |
  | `wrecked` | 1 on the step health reaches 0 (the car is out). Replaced `crash` in 5a4 |
  | `contact` | New wall contacts this step, bumps and hits alike (pushing on into the wall is the same contact). Added in 5a4 |
  | `stopped` | 1 when the car ends the step at speed 0 (idle, or pinned against a wall). Added in 5a4 |
  | `time_up` | 1 on the step the round ends on time |
  | `per_step` | 1 every step (a time cost or bonus) |
  | `distance` | px moved forward |
  | `speed` | Speed as a fraction of max speed |
  | `steering_change` | How much the steering wheel moved |
  | `closest_wall` | Shortest ray distance, as a fraction of the field diagonal |

- **Terms with parameters:** a term is either a weight (`"points": 1.0`) or a weight plus parameters (`"checkpoint_speed": {"weight": 100, "window": 10}`). Each term declares its parameters and their defaults. Parameters are positive numbers. Plain weights keep working, so the format version stays 1.
- Unknown term names, unknown parameters, non-number weights, or a wrong `format` fail early with a clear error. New terms can be added later, and old profiles keep working.
- Shipped profiles: `default` (game points, -100 per wall contact, -500 per full loss of health, and -0.25 per step stopped) and `time_bonus` (`distance_points`, plus `checkpoint_speed` weight 100, window 10 s: a checkpoint is worth up to +100 when reached instantly, 0 after 10 s). `time_bonus` first used `points`, which already includes the game's +100 per checkpoint, so slow pickups still paid +100. Fixed by the `distance_points` term.
- The env takes a profile by name or path. The profile's **full content** is recorded in replays and run configs, so an edited or deleted profile file doesn't lose the record.

### Examples (ideas for experiments, not shipped)

| Profile | Terms | Likely behavior |
|---|---|---|
| cautious | points, big wreck penalty | Slower, keeps away from walls |
| hunter | checkpoints ×300, distance ×0.02 | Beelines to checkpoints, takes risks |
| smooth | points, small steering-change penalty | Fewer zigzags |
| urgent | points, small per-step penalty | Rushes |

## Consequences

- **The game score is never affected.** Agents trained with different profiles still compete on the same leaderboard.
- Agents can exploit weights in unexpected ways. A wreck penalty that's too large can teach "never move", the classic loophole. Replays make such behavior visible.
- The agent profile page (step 6) shows which reward profile trained the agent, next to its skills.
- **Shown in the window:** the top bar has `REWARD <profile name>`, and the side panel's AGENT REWARD section shows the last step's reward and the total this game. The reward is computed in the human demo too, so you can see how a profile would judge your own driving. The panel's SCORE section keeps showing game points.
- **Crash penalty in `default` (2026-09-26, after 5a2):** the first 1M-decision training with points only learned to hunt checkpoints but crashed in 83 % of rounds. A crash ends the round, but with gamma 0.99 the agent only looks about 3 s ahead, where the lost points are worth only about 100 to 200. So `default` adds `"crash": -500` (about 5 checkpoints). Game points and leaderboards are unchanged. Measured on 30 unseen seeds after 1M decisions each: points only scored a mean of 1,750 and survived 17 %; with the penalty, 3,420 and 27 % (the heuristic: 2,402 and 83 %).
- **Damage instead of a crash penalty (2026-09-26, step 5a4):** with car health, a wall hit no longer always ends the round. `default` became `{"points": 1.0, "damage": -500}`: a 25 % hit costs -125, and a full loss of health costs -500, whether in one hit or several. See [decision 016](016-car-health-and-wall-hits.md).
- **A penalty for every wall contact (2026-09-26, step 5a4):** trained with `damage` only, the agent touched a wall about 150 times per round: a bump cost nothing and stopped the car at once, so it used the wall as a free brake. `default` added `"contact": -100` (one checkpoint's worth) per new contact, bumps included. Pushing on into the wall is the same contact, so a pinned car isn't charged every step.
- **A cost for standing still (2026-09-26, step 5a4):** with the contact penalty, the agent survived every round but stayed pinned against a wall once it touched one (42 % of the time, gas held): the penalty charges only a new contact, so staying pinned was free and backing off to touch again cost -100. Standing still with a turn key held was free too. `default` added `"stopped": -0.25` per step at speed 0 (-30/s, about what full-speed driving earns), so backing away from a wall pays at once. It can't be farmed: moving always avoids it.
