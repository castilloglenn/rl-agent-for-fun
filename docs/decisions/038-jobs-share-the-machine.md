# 038: Jobs share the machine

**Date:** 2026-09-30. **Status:** Accepted. Built in steps: fixes 1 and 2 so far; 3 to 5 follow.

## Context

On 2026-09-30 a two-step training plan (create, then train rookie-to-arena) started its training step 141 times in 4 s. Starting a step refreshed the window, the refresh ticked every chain, and the chain didn't know its new job yet, so it started the step again, until a RecursionError killed the control center. The 141 trainings kept running without it, and the Mac (10 cores, 16 GB, memory already at 83%) hung until a restart. The vitals log (decision 024) showed it: 141 `start` notes, no `exit`, no `quit`.

One training on its own is light: about 1 core (11% of the machine) and 0.2 GB.

## Decision

Longer waits are fine; a hung machine never is. Progress stays visible.

1. **Each chain step starts once** (`chains.py`): a tick from inside a start is ignored.
2. **Heavy jobs run at a low priority** (`src/utils/resources.py`): training, resuming, evaluation, and imitation lower their own priority to nice 10, so the system and the windows always come first, and cap torch's threads to leave 2 cores free. It's in the process itself (`app.py`), so `make train` in a terminal gets it too. On this Mac torch already uses 4 threads, so the cap changes nothing here (and exact resume stays identical).

## Consequences

- A busy machine makes training slower instead of the machine slower. The first printed line says so: `Low priority (nice 10), torch threads 4: ...`.
