# 029: Editing the named files in the control center

**Date:** 2026-09-28. **Status:** Accepted. Implemented in roadmap step 6d1 (`src/control/files.py`, `files_tab.py`).

## Context

Everything customizable is a named JSON file ([decision 010](010-decouple-before-file-formats.md)): reward profiles, rules, trainers, models, datasets, and suites. Changing one meant a text editor, and a mistake only showed when a command loaded it. Step 6d1 edits them in the control center, checked as you type.

## Decision

- **A file is a list of fields, by path:** `scoring.checkpoint`, `collisions.health`, `scenarios.1.episodes`. Numbers, text, and lists (`64, 64`) are typed; choices are dropdowns (a dataset's include, a model's activation, a suite scenario's stage and rules); true/false is a dropdown. Values tied to code or to the file's shape are shown but not edited: the name (the file's name), a trainer's algorithm, a model's observation version and actions, a scenario's kind. `format` is hidden.
- **Reward profiles list every known term,** so a term is added by typing a weight and dropped by clearing it; a term's parameters sit under it (blank: its default).
- **Checked with the commands' own validators** (`from_dict` of each kind), at most every 0.3 s while typing. The first problem shows in red and Save stays disabled until the file is valid. The suite's validator loads torch (about 1 s, once).
- **Saving keeps the repo's layout:** flat objects inline up to 2 levels deep when the line fits in 100 characters, everything else one value per line, 2-space indents. This reproduces all the repo's files byte for byte, so saving an unchanged file changes nothing in git.
- **Suites get the next version** when a save changes them, so old scores (`box-v1`) never mix with new ones (`box-v2`). The Agents tab now reads the suite's current version instead of a fixed `box-v1`.
- **Duplicate as…** makes a copy under a new name (a new suite starts at version 1), the usual way to try a variant. **Delete** moves the file into the trash ([decision 027](027-trash.md)), asking first; the defaults the code relies on can't be deleted (reward default, rules standard, trainers default and imitate, model small, dataset mine, suite box).
- **Nothing is lost silently:** switching files or kinds with unsaved changes asks DISCARD CHANGES?, and quitting says which file has them. The header says when a file is tracked by git and that changes apply to future runs only (runs and replays keep their own copy).
- Stages aren't here: the map editor (step 7) edits them. No new make targets: in a terminal these are plain JSON files.

## Consequences

- Only keys already in a file show (plus every reward term). A key a file doesn't have yet is added in a text editor.
- After a suite's new version, agents show no suite scores until evaluated again (`make eval`).
