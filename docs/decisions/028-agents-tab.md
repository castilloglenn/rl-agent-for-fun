# 028: The Agents tab: roster, profile, leaderboard, and deleting agents

**Date:** 2026-09-28. **Status:** Accepted. Implemented in roadmap step 6c (`src/control/agents_tab.py`, `agents_data.py`, `radar.py`, `trash.py`).

## Context

Agents keep everything about themselves in files: `profile.json` (summary, phases, best, milestone), suite results per checkpoint, and history ([decision 018](018-agent-history-and-profile.md)). The terminal shows them one at a time (`make agent`). Step 6c shows them all, side by side, with a fair ranking.

## Decision

- **The roster, two views:** **Cards** (two per row, scrolling), each with the name, leaderboard place, best suite score and its multiple of the heuristic's, model, decisions and training time, a mini skill radar, and badges (TRAINING, MILESTONE, BRANCHED, FROM YOUR DRIVING). Sorted by score, newest, name, or decisions. Or the **Leaderboard**: agents ranked by best suite score (same scenarios, same seeds), with the heuristic and random as dimmed, unranked reference rows, and unscored agents last.
- **High scores**, under the leaderboard: the best 5 single rounds per stage, rules, and round length, from runs' best episodes and your recordings (their headers, read once). Marked as one round each, not a ranking, since a seed can be easy.
- **The profile:** model, decisions, training time, created, milestone (or TRAINING now), a **skill radar** of the best checkpoint, a **skill history** chart (one suite metric per checkpoint, picked from a dropdown, with the heuristic's level), and the **lineage** (how it started, then each phase with its run, status, and "(run deleted)" or a parent "(deleted)").
- **The radar's six axes, each 0 to 1:** score and checkpoint hunting relative to the best among all agents and the heuristic; survival, braking, intact (1 − wreck rate), and clean (1 / (1 + wall contacts per round)). The heuristic is drawn as an outline.
- **Buttons use what exists:** Watch best, Showcase, Evaluate (Commands tab actions), Open run (the Runs tab, with the phase's run), Train more (the Training tab, set to this agent), Branch best (the Training tab, branching from its best checkpoint), and Delete agent.
- **Deleting an agent** (the roadmap's rules, [decision 027](027-trash.md)'s trash): one entry holding `agents/<id>`, its training and imitation runs, and the episode runs it drove. Agents branched from it stay. Refused while any of its runs is live; the button is also disabled while a Training tab chain works on it. The box lists the folders that move, the branched agents that stay, and its leaderboard place. `make delete_agent AGENT=id`, and "Delete an agent" in the Files group.
- **Reading:** profiles, results, and summaries every 2 s, without torch.

## Consequences

- One stage exists, so there's no map filter or specialty yet (step 7 brings them).
- A single suite (box v1) feeds the radar and the ranking. A second suite would need a picker.
