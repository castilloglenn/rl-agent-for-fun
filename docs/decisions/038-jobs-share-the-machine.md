# 038: Jobs share the machine

**Date:** 2026-09-30. **Status:** Accepted. Built in steps: fixes 1 to 4 so far; 5 follows.

## Context

On 2026-09-30 a two-step training plan (create, then train rookie-to-arena) started its training step 141 times in 4 s. Starting a step refreshed the window, the refresh ticked every chain, and the chain didn't know its new job yet, so it started the step again, until a RecursionError killed the control center. The 141 trainings kept running without it, and the Mac (10 cores, 16 GB, memory already at 83%) hung until a restart. The vitals log (decision 024) showed it: 141 `start` notes, no `exit`, no `quit`.

One training on its own is light: about 1 core (11% of the machine) and 0.2 GB.

## Decision

Longer waits are fine; a hung machine never is. Progress stays visible.

1. **Each chain step starts once** (`chains.py`): a tick from inside a start is ignored.
2. **Heavy jobs run at a low priority** (`src/utils/resources.py`): training, resuming, evaluation, and imitation lower their own priority to nice 10, so the system and the windows always come first, and cap torch's threads to leave 2 cores free. It's in the process itself (`app.py`), so `make train` in a terminal gets it too. On this Mac torch already uses 4 threads, so the cap changes nothing here (and exact resume stays identical).
3. **Limits and a dead switch** (`jobs.py`, `JobLimits`, set in `get_control_config()`):
   - **At most 2 heavy jobs at once.** One more is refused, with the running ones named. Watching and driving aren't limited. Two, not one: you ran two trainings side by side on 2026-09-30 without trouble (about 1 core each).
   - **The dead switch:** more than 5 starts within 10 s means something is looping, whatever the cause. Every job stops (Ctrl+C, so training keeps its resume state), and starts are refused until you reset it. A DEAD SWITCH box says why: Enter resets, Esc keeps it on, and the next start asks again. The vitals log notes the trip and the reset. With it, the 2026-09-30 loop would have ended after 5 jobs instead of 141.
   - A refused start doesn't refresh the window, so the error path can't tick the chains again.
4. **Memory** (`jobs.py`, with the vitals bar's readings):
   - **No heavy job starts while memory is red** (95 % in use, the vitals bar's red). Watching and driving still start.
   - **The dead switch trips when memory stays red for 5 s while our jobs hold at least 1 GB.** macOS sits around 80 % with nothing heavy running, and two trainings hold about 0.4 GB, so it only fires when our jobs are filling memory, as the 141 trainings did. Memory filled by other apps only blocks new heavy jobs; it never stops yours.

## Consequences

- A busy machine makes training slower instead of the machine slower. The first printed line says so: `Low priority (nice 10), torch threads 4: ...`.
