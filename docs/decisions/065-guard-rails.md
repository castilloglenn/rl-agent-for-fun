# 065: Guard rails against features breaking each other

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7h (`src/app_checks.py`, `-check` in `app.py`, `tests/test_guard_rails.py`).

## Context

As features grew, some broke others they never touched directly: a curriculum added to the shared Stage list reached the recorder, which couldn't play one (a crash halfway in); the Evaluate action and the `--suite` flag kept defaulting to the `box` suite after it was deleted; numbers like "8 rays" and "15 inputs" were repeated instead of derived; a Training tab pick raced its own rebuild. Each feature's own tests passed: the bugs lived where features meet.

## Decision

- **Every command checks its arguments first** (`app_checks.problems`, called at the start of `app.py`'s dispatch): each named file it reads exists (stage, rules, reward, trainer of the right kind, model, dataset, suite, the showcase's skill), its driver is one it can use (not the keyboard without a window), and its stage is a kind it plays: training takes a stage, a mix, or a curriculum; recording a stage or a mix; everything else one stage. A problem is one plain line, never a crash halfway in. `app.py -check ...` checks and stops (prints "check: ok").
- **Three guard-rail tests**, cheap (under a second together), on what is offered, not on what we remember to test:
  - every default in the Commands tab's forms and the Training tab is one of its own choices;
  - every action, run with every choice its named-file and driver dropdowns offer, passes the check;
  - every make target's command (via `make -n`) passes the check;
  - and every kind of stage, given to each command that takes a stage, either works or is refused in plain words.
- **A consumer sweep in every step:** adding a value to anything shared (a dropdown, a kind, an input, a config key), every place that uses it is checked, and the report names them.
- One source of truth: numbers that follow from others are derived (`len(OBSERVATION_NAMES)`, `OBSERVATION_NAMES.index("speed")`).

## Consequences

- It already caught one more: episodes (`-run`) on a mix used to crash partway; now it's refused with a line that says a mix is for training and recording.
- A new command that reads a named file or a kind adds it to `app_checks`, and the guard rails cover it from then on.
