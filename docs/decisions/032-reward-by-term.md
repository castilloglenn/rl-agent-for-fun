# 032: The agent reward by term, in a bar under the field

**Date:** 2026-09-28. **Status:** Accepted. Implemented in `src/envs/maze_car/rewards.py` (`contributions`), `env.py`, `src/render/panels.py` (`draw_reward_bar`), and `layout.py`.

## Context

The game window's AGENT card showed one number, the agent reward this game. It hid where it came from: whether a round's reward was mostly points, or points minus big wall-contact costs. You asked to see gains and costs apart.

## Decision

- **Each term's share:** `RewardProfile.contributions(events)` gives each term's weight × value for a step, and the reward is their sum (the profile's call now sums them: the same numbers, bit for bit, a test checks). The env adds them up over the game (`round_terms`), and `RewardStatus` carries them with the profile's weights.
- **Gains and costs:** a term goes by the sign of its sum so far; at 0, by its weight's sign. A term like `speed` can move from gains to costs (reversing makes it negative). Each group's terms are sorted by size.
- **A reward bar under the field,** the field's full width: `REWARD default · GAINS +3,901.0 points +3,901.0 · COSTS -1,480.0 contact -1,200.0 · damage -250.0 · stopped -30.0 · NET +2,421.0`, gains in green and costs in red. When less fits, zero terms go first, then the terms past the first of a group are summed as "other", then the terms (the totals stay).
- **Not in the AGENT card:** it had room for about 5 rows and the breakdown needs 9 to 11. The card keeps profile, reward this game (the net), step, and sim rate.
- **The window grows 60 px** (the bar and its gap). In replays and the showcase it sits under the playback bar. Every game window shows it: live play (it's what an agent would get for your driving), watching a driver, replays, and the showcase. `window.reward_bar` (default on) is a display setting.
- ASCII plus and minus signs (the font lacks the typographic minus), one decimal, and a plain 0.0.

## Consequences

- Reward values, training, replays, and the behavior fixtures are unchanged: the env only adds up what the profile computes.
- The same sums per episode, charted in the Runs tab, are planned (roadmap 6e).
