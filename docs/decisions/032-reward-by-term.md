# 032: The agent reward by term: gains, costs, and the biggest cost

**Date:** 2026-09-28. **Status:** Accepted. Implemented in `src/envs/maze_car/rewards.py` (`contributions`), `env.py`, and `src/render/panels.py` (the AGENT card).

## Context

The game window's AGENT card showed one number, the agent reward this game. It hid where it came from: whether a round's reward was mostly points, or points minus big wall-contact costs. You asked to see gains and costs apart.

## Decision

- **Each term's share:** `RewardProfile.contributions(events)` gives each term's weight × value for a step, and the reward is their sum (the profile's call now sums them: the same numbers, bit for bit, a test checks). The env adds them up over the game (`round_terms`), and `RewardStatus` carries them with the profile's weights.
- **Gains and costs:** a term goes by the sign of its sum so far; at 0, by its weight's sign. A term like `speed` can move from gains to costs (reversing makes it negative).
- **All of it in the AGENT card,** which has room for 5 rows (the window's height follows the field): the profile in the header (`AGENT · default`), then Gains (green), Costs (red), Net, the biggest cost by name (`contact -1,200.0`, or none), and the simulation in one row (`step 7,200 at 120/s`).
- **Tried first, then dropped:** a reward bar under the field with every term. It repeated the card's profile and net, and made the window 60 px taller, so the card took it over.
- ASCII plus and minus signs (the font lacks the typographic minus), one decimal, and a plain 0.0.

## Consequences

- Reward values, training, replays, and the behavior fixtures are unchanged: the env only adds up what the profile computes.
- Only the biggest cost is named in the window. Every term per episode, charted in the Runs tab, is planned (roadmap 6e).
