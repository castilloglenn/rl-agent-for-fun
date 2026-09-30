# 044: Data in sync across the control center

**Date:** 2026-09-30. **Status:** Accepted. Built in roadmap 7c7 (`src/control/watch.py`, `on_data` in each tab).

## Context

Each tab re-read its lists on a timer (runs, agents, maps), but dropdown choices were fixed when a form was built: the Training tab's Agent, Stage, Model, and Dataset fields, the Maps tab's driver picker, the Commands tab's fields, and the Files tab's file list. A deleted agent stayed in the Training tab's Agent dropdown until that form happened to be rebuilt.

## Decision

- **One watcher, for every kind of data and every source:** `DataWatch` looks at each data folder's modification time (agents/, each agent's checkpoints/, runs/, recordings/ and each player's, trash/, and every named-file folder with its `user/` twin). A folder's time changes when anything in it is added, removed, or renamed, so a delete in a tab, a job writing a run or a checkpoint, a terminal command, and a game window are all caught the same way, within half a second. About 20 `stat` calls: 0.09 ms per look (measured), and nothing is read unless something changed.
- **Each tab rebuilds only what's touched** (`on_data(kinds)`): its dropdowns and lists for those kinds, keeping your picks that still exist. A pick that's gone falls back to its default and the tab says so ("rookie is gone"). The Files tab updates its list in place, so an open file keeps its unsaved edits (unless it's the one deleted).
- **Never under your cursor:** while a dropdown is open, changes wait. A tab you're not looking at queues them and applies them when you open it.
- **Not covered, on purpose:** edits inside an existing file (an agent's scores in its profile) don't change a folder's time; each tab's own 1 to 2 s timer re-reads those, as before.

## Consequences

- The Commands tab's fields now also show your files' "· yours" tag (a 7d1b miss), and keep their values when rebuilt.
- The Commands tab's choices come from the repo's files (not a test root), as before.
