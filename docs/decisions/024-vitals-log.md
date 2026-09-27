# 024: A small vitals log, for looking into crashes

**Date:** 2026-09-27. **Status:** Accepted. Implemented with roadmap step 6b1 (`src/control/vitals.py`, `make vitals`).

## Context

The control center shows the machine's vital signs live (CPU, memory, battery, disk, our jobs' share, [decision 022](022-control-center-in-pygame.md)), but nothing keeps them. After a crash (a training killed, the laptop freezing, the control center closing), there's no record of what the machine was doing. The record must stay small: cheap on disk, and cheap to read in an analysis (tokens).

## Decision

- **`logs/vitals.csv`**, gitignored, written by the control center from the readings it already takes. No extra process.
- **A row every 10 s**, and at once when a stat changes level (normal, caution, danger), with the note "level change", so a short spike isn't missed.
- **Short rows** (about 45 bytes): time, CPU %, our jobs' CPU %, memory used (GB) and %, our jobs' memory (GB), battery %, plugged in (1/0), free disk (GB), running jobs, note.
- **Events as notes:** `open` and `quit` for the control center, and each job's `start #N <label>`, `pause #N`, `resume #N`, `stop #N` (Ctrl+C), `end #N` (a second stop), and `exit #N code C`. A log that ends without `quit` means the control center itself stopped abruptly, and an exit code of -9 means the process was killed (often: out of memory).
- **Capped:** past 100 KB, the file becomes `vitals.1.csv` (replacing the older one), so both stay near 200 KB, about 2,200 rows or 6 hours each. The last 100 rows are about 1.5k tokens.
- **`make vitals`** (and the Develop action "Vitals log") prints the last 30 rows, across both files.
- Tests never write it: `ControlCenter` keeps no log unless `logs_dir` is given (`app.py` passes `logs/`).

## Consequences

- Only while the control center is open: a `make train` in a terminal with the control center closed isn't logged.
- Job exits are noted from each job's output thread, so the log has a lock.
