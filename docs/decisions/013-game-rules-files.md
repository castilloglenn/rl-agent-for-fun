# 013: Game rules as files, next to stages and reward profiles

**Date:** 2026-09-25. **Status:** Accepted, not implemented (roadmap step 4g).

## Context

The rules of a game were scattered through config: round length in `config.round.seconds`, rounds per game in `config.game.rounds`, and scoring in `config.rewards`. They could only be changed one flag at a time, and `config.rewards` (the game's scoring) was easily confused with reward profiles (what an agent learns from, [decision 011](011-reward-profiles.md)).

## Decision

Game rules become named files in `rules/<name>.json`, starting with `rules/standard.json`, which holds today's exact values:

```json
{
  "format": 1,
  "name": "standard",
  "description": "One 60 s round, points for distance and checkpoints.",
  "round_seconds": 60,
  "rounds": 1,
  "scoring": {"distance_step": 10, "checkpoint": 100}
}
```

That gives three separate, swappable things, each a named file:

| File type | Answers | Examples |
|---|---|---|
| Stage (`stages/`, [decision 009](009-stage-format-and-spawn-schedules.md)) | *Where* the game is played | box, s_curve |
| **Rules** (`rules/`) | *How* the game is played and scored | standard, sprint, marathon |
| Reward profile (`rewards/`, [decision 011](011-reward-profiles.md)) | What an *agent* learns from | default, cautious |

- A game is set up by **stage + rules + seed** (plus the drivers). The agent's reward profile is separate and never changes the game.
- Rules are chosen with one setting, `--rules <name>`, and shown in the top bar (`RULES <name>`).
- `format` is versioned, so later rules (fuel, hazards, crash behavior, between-round rules) can be added without breaking old files.
- Replays **embed the full rules**, like stages. Run configs record them.
- `config.round`, `config.game.rounds`, and `config.rewards` go away. The config keeps `game.seed` and names the rules file (`config.rules = "standard"`), like it names the stage.

## Consequences

- **Leaderboards compare scores only within the same stage + rules.** A 120 s round naturally scores about twice a 60 s one.
- The evaluation suite fixes its rules per scenario, like its stages and seeds.
- With `standard`, nothing behaves differently. The behavior fixtures only change their config header.
