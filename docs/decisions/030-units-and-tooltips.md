# 030: Units in the editor, and tooltips across the control center

**Date:** 2026-09-28. **Status:** Accepted. Implemented after step 6d1 (`src/control/help.py`, `tooltips.py`).

## Context

The control center shows many terms that only make sense with context: file fields (`collisions.safe_speed`, `gae_lambda`), training charts (entropy, KL divergence), skills (clean, intact), leaderboard columns, and the vital signs' thresholds. Numbers in the Files tab had no units.

## Decision

- **Units inside the fields:** dim, at the right end of a typed field, so they never move the value: s, px/s, health per px, decisions, neurons per layer, steps per decision, °, and for reward terms what one unit is ("per contact", "per step stopped"). The Commands and Training tabs show them too (Round seconds: s, Episodes: rounds, FPS cap: fps).
- **One tooltip system of our own,** since most labels, legends, cards, and the vital signs strip are drawn by hand (pygame_gui's tooltips only cover its widgets). Resting the mouse 0.5 s on a target opens a small box by it (wrapped at 320 px, accent border). It closes when the mouse leaves, and stays hidden while a dropdown or a confirmation box is open.
- **A marker where help exists:** a small dim circled "i", drawn by hand after the label. Places where a marker would crowd or break alignment get the tooltip without one: legend items, radar axis labels, leaderboard column headers, badges, the "× heuristic" ratio, the run status, and the vital signs strip.
- **How it's wired:** while drawing, each tab registers "this rectangle has this help"; after everything else, the window draws the one tooltip under the mouse.
- **The words live in one file,** `help.py`: every file field by path (`scenarios.*.episodes` for any scenario) with its unit, every reward term and parameter, the form fields, and topics (charts, statuses, skills, columns, badges, vital signs).
- **Tests keep the texts honest:** every field of every file in the repo has help, every help key is a real field, every reward term is covered, every form field has help, and every topic a tab asks for exists.

## Consequences

- A new field or term needs a help text, or a test fails and says which.
- The game window isn't covered: it has its own `?` shortcuts box ([decision 021](021-window-layout-on-four-sides.md)).
