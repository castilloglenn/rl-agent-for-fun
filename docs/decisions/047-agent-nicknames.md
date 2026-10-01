# 047: Agent nicknames

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7c10.

## Context

You wanted to name agents by their behavior ("Reverse Guy") and change the name as they learn. An agent's id is its folder name, and many things point to it: its runs and their configs, other agents' "branched from", replay and high-score labels, the trash. A true rename would rewrite all of them, and couldn't happen while it trains.

## Decision

- **A nickname, not a rename:** your display name for an agent, set (or cleared, with an empty name) anytime, even while it trains. Its id never changes, so commands, runs, lineage, and history keep working.
- **Stored as a history event** (`set_nickname` records `nickname`), and the profile takes the latest one. The profile is rebuilt from the history after every event, so the nickname survives every rewrite, including a training job's, and the history keeps every name it had. One line, at most 40 characters, spaces tidied.
- **Shown wherever the agent is named:** the Agents tab's cards, leaderboard, and profile (the nickname big, its id beside it), every agent dropdown ("Reverse Guy · agent-1", the value still the id), `make agent` and `make agents`, and the showcase's cards.
- **Set in the Agents tab profile:** a Nickname field and button (Enter works too). No `make` target: targets take one parameter.

## Consequences

- Old runs, replays, and run folder names keep the id: they're records.
