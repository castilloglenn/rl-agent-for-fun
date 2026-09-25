# 009: Stage files, and spawn schedules decided by stage + seed

**Date:** 2026-09-25. **Status:** Implemented in roadmap step 4b (`src/sim/stage.py`, `src/sim/spawning.py`, `stages/box.json`), with 8 candidates per slot.

## Context

The playing area was defined implicitly: the field size in config (with a leftover origin at 22.5, 97.5), the car's start pose hard-coded in `create_start_car`, and checkpoint rules in config. Replays, runs, and the evaluation suite all need to reference a stage, and future stages will be bigger and custom-made.

Checkpoint spawns came from the seed, but used rejection sampling around the car's position. The number of random draws then depended on the driving, so **two drivers with the same seed got different checkpoint sequences**. That's fine for replays (same inputs, same result), but unfair for comparing drivers.

## Decision

### Stage files

A stage is a JSON file (`stages/<name>.json`), starting with `stages/box.json`:

```json
{
  "format": 1,
  "name": "box",
  "size": [855, 480],
  "walls": [],
  "spawns": [{"x": 213.75, "y": 240, "angle": 0}],
  "checkpoints": {
    "mode": "random",
    "radius": 15,
    "border_margin": 40,
    "min_car_distance": 100
  }
}
```

- Stage coordinates have their **origin at (0, 0)**.
- `format` is versioned, so later stages can add fields without breaking old ones.
- The size isn't fixed. Stages bigger than the window get a camera (roadmap step 7).
- Replays **embed the whole stage**, so they keep working if the file is later edited or deleted.

### Spawn schedules

Stage + seed decide every spawn, independent of the driving:

- **`random` mode:** the seed generates the sequence of spots up front. Each slot has a few backup candidates. When the next spot is too close to a car, the first backup far enough away is used, which is rare, so almost every driver gets the identical sequence.
- **`scripted` mode:** the stage lists exact spots (`"points": [[x, y], ...]`), for handcrafted stages such as tutorials or benchmark courses. Fuel will add timings (`"at": seconds`).
- **One random stream per spawner**, derived from the seed and the spawner's name (checkpoints, fuel, ...). Adding a spawner never changes another spawner's sequence for existing seeds.

## Consequences

- Stage file + seed = the same round for every driver, which the leaderboards and evaluation suite rely on.
- The field's world coordinates shift by the old offset, so behavior fixtures are regenerated once. Physics distances are unchanged.
- `config.field` and `config.checkpoint` move into the stage file. The config keeps game-wide rules (round length, rewards, driving).
