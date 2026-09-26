# 016: Car health and wall hits by impact speed

**Date:** 2026-09-26. **Status:** Implemented in roadmap step 5a4 (`src/sim/collisions.py`, `Health` in `src/sim/components.py`, `collisions` in the rules files).

## Context

Any wall contact wrecked the car instantly. A light scrape and a full-speed crash ended the round the same way. That's harsh for players, and it gives an agent nothing to learn between "never touch" and "gone": the trained agent never braked (0 % of its decisions).

## Decision

- **Health, set by the rules file**, like round length:

  ```json
  "collisions": {"health": 100, "safe_speed": 60, "lethal_speed": 240, "scrape_damage": 0.1}
  ```

  Damage = `health × (impact − safe_speed) / (lethal_speed − safe_speed)`, from none up to all of it. `rules/classic.json` keeps instant wrecks (`safe_speed` = `lethal_speed` = 0).
- **Impact speed is the speed into the wall** (the part of the car's velocity toward the border it touched), so grazing hurts less than a head-on hit. A turn that pushes a corner into the wall is a hit at that corner's speed, and the turn doesn't happen.
- **The car slides along the wall** (changed from "stop" the same day, see Consequences): on the first step of a contact it loses the part of its motion into the wall, and its speed shrinks to the part along it. A head-on hit stops it exactly where it touched. Pushing on into the wall is the same contact: no more impact damage, but **scraping costs `scrape_damage` health per px slid** (1 per 10 px), so riding a wall wears the car down. No bounce: the car only moves along its heading, and a bounce would need a separate velocity. A wrecked car doesn't slide.
- **Wording:** a *bump* does no damage, a *hit* costs health, and a *wrecked* car (health 0) is out of the round. "Crash" is gone from code, events, and HUD.
- **Agents:** health joins the observation (15 values, still version 1, since there's no old data to stay compatible with). Reward terms `damage` (share of health lost), `wrecked`, `contact` (new wall contacts), and `stopped` (speed 0) replace `crash`. The default profile is `{"points": 1.0, "damage": -500, "contact": -100, "stopped": -0.25}`: a full loss of health costs -500 however it happens, every new wall contact costs -100, even a harmless bump (without it, the agent used bumps as a free brake, about 150 per round), and each step stopped costs -0.25 (without it, the agent stayed pinned against a wall with gas held). See [decision 011](011-reward-profiles.md).
- **Window:** a HEALTH gauge at the top right of the top bar (the side panel was full, and fuel joins the gauge in step 9). A hit car blinks red, in simulation time, so replays show it the same way.
- **No compatibility code:** this is the alpha. Old agents, runs, and recordings were deleted, and there's no fallback for rules files without `collisions`.

## Consequences

- Under `classic`, all 14 behavior scenarios matched the old fixtures at every step, so the old instant-wreck logic is still exactly there. Under `standard`, only the wording changed in the fixtures (the scenario's full-speed hit still wrecks).
- Recordings made before 5a4 can't replay, which matters for imitation (5b): record fresh ones.
- **Why sliding:** with "stop", a car touching the wall at a shallow angle was glued. Each gas press pushed its corner into the wall and reset its speed to 0, and at speed 0 it can't turn. Its rays didn't show the contact either (a corner isn't on any ray's path). A trained agent spent 41 % of its time glued like this, gas held. Shrinking the speed on every step of a contact didn't help either (it settled near 1 px/s), so only the first step of a contact takes the impact.
- The event log shows one bump or hit per contact, not one per step.
- **Measured (30 unseen seeds, default reward and trainer):** with sliding, the agent is never glued (pinned 41 % → 4 %, stopped 41 % → 0 %) and reverses when needed. It learns later than with "stop" (1M decisions: mean 2,244, 70 % survival), but a second 1M phase reaches mean 3,216, 22.2 checkpoints, and 83 % survival at 1.5M (heuristic: 2,402, 15.8, 100 %). At 2M it began riding walls (touching one 18 % of the time, 11 contacts per round), a possible next reward fix.
- **Scrape damage (added the same day):** with free scraping, the 2M-decision agent rode walls (touching one 18 % of the time). A scrape now costs 0.1 health per px, which the `damage` reward charges at once (-0.5 per px slid, against +0.1 per px for driving).
- **Measured after scraping and reward scaling (30 unseen seeds, 2M decisions, two agents trained side by side):**

  | Agent | Mean score | Checkpoints | Survived | Time on a wall |
  |---|---|---|---|---|
  | Heuristic | 2,402 | 15.8 | 100 % | 0 % |
  | `reward_scale` 1, at 1.5M / 2M | 3,907 / 4,363 | 27.1 / 30.2 | 90 % / 83 % | 3 % / 1 % |
  | **`reward_scale` 0.01, at 1.5M** / 2M | **5,234** / 5,089 | **35.3** / 34.1 | **100 %** / 90 % | 0 % / 0 % |

  Scraping ended wall-riding (18 % → 0 to 3 %). Reward scaling learned faster (4,361 already at 1M) and better, so it became the default. The best checkpoint isn't always the last one (1.5M beat 2M): the evaluation suite (5a5) will pick it.
