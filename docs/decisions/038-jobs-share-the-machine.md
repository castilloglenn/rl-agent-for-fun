# 038: Jobs share the machine

**Date:** 2026-09-30. **Status:** Accepted. Built in six steps (fixes 1 to 6), all on 2026-09-30.

## Context

On 2026-09-30 a two-step training plan (create, then train rookie-to-arena) started its training step 141 times in 4 s. Starting a step refreshed the window, the refresh ticked every chain, and the chain didn't know its new job yet, so it started the step again, until a RecursionError killed the control center. The 141 trainings kept running without it, and the Mac (10 cores, 16 GB, memory already at 83%) hung until a restart. The vitals log (decision 024) showed it: 141 `start` notes, no `exit`, no `quit`.

One training on its own is light: about 1 core (11% of the machine) and 0.2 GB.

## Decision

Longer waits are fine; a hung machine never is. Progress stays visible.

1. **Each chain step starts once** (`chains.py`): a tick from inside a start is ignored.
2. **Heavy jobs run at a low priority** (`src/utils/resources.py`): training, resuming, evaluation, and imitation lower their own priority to nice 10, so the system and the windows always come first, and cap torch's threads to leave 2 cores free. It's in the process itself (`app.py`), so `make train` in a terminal gets it too. On this Mac torch already uses 4 threads, so the cap changes nothing here (and exact resume stays identical).
3. **Limits and a dead switch** (`jobs.py`, `JobLimits`, set in `get_control_config()`):
   - **At most 2 heavy jobs at once.** One more is refused, with the running ones named. Watching and driving aren't limited. Two, not one: you ran two trainings side by side on 2026-09-30 without trouble (about 1 core each). (Fix 6 replaced the fixed 2: the machine decides.)
   - **The dead switch:** more than 5 starts within 10 s means something is looping, whatever the cause. Every job stops (Ctrl+C, so training keeps its resume state), and starts are refused until you reset it. A DEAD SWITCH box says why: Enter resets, Esc keeps it on, and the next start asks again. The vitals log notes the trip and the reset. With it, the 2026-09-30 loop would have ended after 5 jobs instead of 141.
   - A refused start doesn't refresh the window, so the error path can't tick the chains again.
4. **Memory** (`jobs.py`, with the vitals bar's readings):
   - **No heavy job starts while memory is red** (95 % in use, the vitals bar's red). Watching and driving still start.
   - **The dead switch trips when memory stays red for 5 s while our jobs hold at least 1 GB.** macOS sits around 80 % with nothing heavy running, and two trainings hold about 0.4 GB, so it only fires when our jobs are filling memory, as the 141 trainings did. Memory filled by other apps only blocks new heavy jobs; it never stops yours.
   - Disk and battery: no heavy start while either is red (under 5 GB free; under 20 % and unplugged). CPU trips nothing: training is meant to use it, and low priority (2) keeps the system first.
5. **Every heavy job guards itself** (`src/control/guard.py`, started by `app.py`), so the last gate needs neither the control center nor a background service:
   - **At start:** it doesn't start if `max_heavy` heavy jobs of this project already run (found by their command line and folder), nor on a red reading. The oldest jobs run, so even a burst ends with `max_heavy` of them: the 141 would have been 2, even without fixes 1 and 3, and it holds for `make train` in terminals too.
   - **While it runs,** a watcher thread checks every second and stops the job like Ctrl+C (training keeps its resume state) when the program that started it ended (the control center closed or crashed: the job's parent becomes launchd, pid 1), the disk or the battery (unplugged) turns red, or memory stays red for 5 s while this project's heavy jobs hold 1 GB. If Ctrl+C hasn't ended it after 60 s, it ends it.
   - **`make stop_all`** (and "Stop every job" in the control center, after a confirmation) is the manual switch: every job of this project but the control center, Ctrl+C first, then ended after 10 s.
   - Not a launchd service: it would run all the time and need installing. A guard inside each job exists exactly while a job runs.
   - A job whose parent ends stops, so a training started with `nohup` stops when its terminal closes. Keep the terminal (or the control center) open while it trains.
6. **The machine decides how many** (`guard.py`: `estimate_gb`, `room_for`, `job_limit_gb`), in the control center and in each job's own start gate:
   - **Memory estimate:** 0.30 GB plus 40 bytes per parameter of the job's model (policy and value networks: `model_params`, checked against the real network). Measured the same day: 0.31 GB for 64x64 and 128x128, 0.62 GB for 2048x2048, 1.41 GB for 4096x4096 (the estimate says 1.65). The model comes from the command: the agent's `model.json` (train, eval, imitate, resume, a run with an agent driver), else `--model` for a new agent.
   - **A heavy job starts only if its estimate fits while memory stays below amber (88 %),** and fewer heavy jobs run than the cores minus the 2 kept free (8 on a 10-core Mac). That count is also the backstop against runaways. `jobs.max_heavy` can set a fixed number instead.
   - **Per-job cap:** the guard stops a job that holds more than twice its estimate plus 0.5 GB: its estimate was badly wrong. A fixed share of memory (first proposed: 25 %) would have refused big models even with room for them.
   - **Runs count as heavy** (`-run`): with an agent driver they keep the CPU busy for minutes.
   - Known edge: two starts in the same second both see the same free memory. The per-job cap and the memory trip catch the overshoot.

## Consequences

- A busy machine makes training slower instead of the machine slower. The first printed line says so: `Low priority (nice 10), torch threads 4: ...`.
