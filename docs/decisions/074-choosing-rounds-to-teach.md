# 074: Choosing which rounds an imitation teaches

**Date:** 2026-10-04. **Status:** Accepted. Part A built in roadmap 7g2 (`src/control/round_picks.py`, `rounds_picker.py`, `training_tab.py`, `form.py`, `src/experiments/datasets.py`, `--recordings`); part B (the preview) planned.

## Context

A dataset read every round of its player. When you set agent_4 to learn your corrections, the `corrections` dataset would have taught all 7 rounds there: 6 from older agents (agent_1-1 and agent_3), and 6 on test maps (`skill_detour`, `skill_gaps`), where teaching makes the Detour and Threading scores measure memory, not skill. Nothing showed which rounds a clone would learn from, and the only way to leave one out was deleting it.

## Decision

- **A "Rounds" row in the Training tab** (imitation modes), under Dataset: "1 of 7 ticked (8.2 s) · Choose…". It opens a box over the tab: a table of the dataset's own rounds (when, map with a "test" tag, the agent and checkpoint watched, your seconds, score), tick boxes, the clicked round's details on the right, and a footer with what's ticked, the corrected moments' weight, the other players' rounds (always taught, unchosen), and a warning for a ticked test map. Space ticks, Up and Down move, Enter uses, Esc cancels.
- **Ticked by default:** every round but one on a test map (not the box: it's a training map too) and a correction of an agent outside this agent's line (itself and the agents it was branched from, from their profiles). Your ticks are kept per dataset and agent while the window is open; rounds recorded since get their default, deleted ones drop out.
- **Filters only hide:** "This agent's" and "Test maps hidden" are on at first; a hidden round keeps its tick, and the footer counts it.
- **To the command:** the ticked rounds' file names go to `-imitate --recordings a,b,...` (a "Recordings" field of the Commands tab's "Clone your driving", blank for all; every round ticked sends none). The dataset gets `only` (its player's rounds only; the `also` players' never), and the run's config records the dataset with it, as it already lists every recording used. `app.py -check` refuses a name that isn't one of the player's rounds. No ticked round blocks the plan.
- **Forms** can have a button row (`Field.button`): shown, not a value.

## Consequences

- Imitation from the Training tab no longer teaches rounds on test maps, or corrections of other agents, unless you tick them. That's also true for `mine` (your own driving): its test-map rounds start unticked.
- `make imitate_corrections` and the Commands tab still teach every round unless given names.
- Part B adds a preview: the round's path on a mini map with your stretches highlighted, a timeline of your takeovers, and watching from the first one.
