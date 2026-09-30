# 037: Watch on the stage it trained on

**Date:** 2026-09-30. **Status:** Accepted. Amends [026](026-checkpoint-box-and-compare.md) (Watch it drive) and [028](028-agents-tab.md) (Watch best).

## Context

Both buttons started "Watch a driver" with only the driver, so the game used its default stage, the box, even for an agent that trained on the arena.

## Decision

- **Runs tab, Watch it drive:** on the stage the run trained on (its config's `stage.name`).
- **Agents tab, Watch best:** on the stage of the agent's newest training phase (imitation phases have none, so they're skipped).
- Either falls back to the box when there's no stage, or its file in `stages/` is gone (`maps_data.watch_stage`).
- The button's tooltip names the stage, so you know before clicking.
