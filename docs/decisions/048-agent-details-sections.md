# 048: The agent details in sections

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7c11 (`src/control/agents_tab.py`, `src/control/style_view.py`, `wrap_name` in `src/control/text.py`).

## Context

The Agents tab's detail panel was one page: the name, three lines of info, the skills radar and its history, the lineage, and the buttons. Each feature squeezed the others (the driving style was a single cut-off line of percentages, the radar labels collided), and a long nickname was cut short. More is coming (7d4's skills chart).

## Decision

- **A fixed header, then sections.** The header always shows the name on up to two lines (wrapped at spaces; only what still doesn't fit gets "…"), the id (under a nickname), model, decisions, training time, and creation date on the next line, and the nickname field. Under it, four sections, one at a time: **Overview** (the milestone, key numbers, and a driving bar with its warning), **Skills** (the radar and the history chart, full height), **Driving**, and **Lineage** (the phases' list, full height). The buttons stay at the bottom for every section.
- **Driving as graphs:** the pedals (forward, brake, coast, reverse) as a stacked bar, with the heuristic's below it for reference and a legend with each share; turning as a left / straight / right split; moving backward as a gauge with a tick at the warning line (40 %), amber past it; and the pedals over the scored checkpoints as a chart. The colors match the Runs tab's style chart (`runs.STYLE_LINES`).
- **Names stay whole:** cards give the name two lines with the id under it (cards grew from 130 to 156 px); a leaderboard cell cut short shows whole on hover.
- **A new feature gets a section, or room in one,** instead of squeezing the page.

## Consequences

- Dropdown lists (pygame_gui) still cut a long "Nickname · id" to the field's width; the field's choice shows whole on hover elsewhere, not inside an open list.
