# 005: Structure the simulation as an ECS (Entity Component System)

**Date:** 2026-09-25. **Status:** Implemented (step 2). Replaces the `sim/` internals from [decision 002](002-sim-render-split.md). The layer split from 002 (sim / env / render / replay / agents) still holds.

## Context

The current code is loosely MVC-inspired, but its sprites both simulate and draw, and all state lives in global singletons. The owner chose ECS over a plain object-based `World`/`Car` core, expecting more entity types later (walls, multiple cars, possibly others).

## Decision

- **Entities** are plain integer IDs, with no behavior.
- **Components** are data-only dataclasses attached to entities.
- **Systems** are functions that run over every entity with a given set of components, in a fixed order.
- **Resources** hold per-world shared data (config, field bounds). They replace the singletons: each world has its own, so several worlds can exist in one process.
- The ECS core is small and written in-house, with no library. The owner chose this for full control. `esper` 3.9 was considered and rejected because:
  - It keeps all world data in module-level globals, so only one world is active at a time (`switch_world`). That conflicts with the "no globals" rule.
  - Tests would have to reset global state between runs.
  - It iterates entities from a `set`, so strict ascending ID order would need `sorted()` in every system.
  - It has no concept of resources.

### First components (mapped from current code)

| Component | Fields (from) |
|---|---|
| `Transform` | angle, x_float, y_float (`CarState`). Since step 3d: float center x, y, and angle |
| `Motion` | speed (was `speed_multiplier`), acceleration_rate (`CarState`). Since step 3b: signed speed, pedal state, and steering wheel position |
| `CarSpec` | base, forward, backward, turn speeds, acceleration unit (`CarState` derived fields). Since step 3b: per-step driving limits from config |
| `Hitbox` | unrotated width/height, and `rect` (`CarState.rect`). **`rect` was also the car's position**, kept so behavior matched exactly during the refactor. Since step 3d: width and height only (the corners come from `car_corners`) |
| `Sensors` | list of rays: relative angle, offset, start, end, distance (`CollisionDistanceState`) |
| `ActionInput` | turn_left, turn_right, move_forward, move_backward (`ActionState`). Since step 3b: turn_left, turn_right, gas, reverse, brake |
| `Renderable` | color, size (read only by rendering) |

### System order per step

1. **Steering:** turn by the action, reversed while moving backward.
2. **Movement:** forward/backward and sub-pixel carry, clamp to the field, stop when clamped, zero speed when idle.
3. **Sensors:** cast rays from the final position.
4. Later: **Collision** (walls, then car vs car).

Rendering is a system too, but it runs outside the simulation step and only reads components, so switching it on or off can't change results.

Controllers (keyboard, agent, replayer) write `ActionInput` before each step.

### Target layout

```
src/ecs/          World: entity IDs, component stores, resources, system order
src/sim/          components.py, systems/, factories.py (create_car, create_field)
src/render/       render system (pygame drawing, debug overlay)
src/envs/         Gymnasium-style env wrapping a World
src/replay/       Recorder / Replayer
src/agents/       torch agent
app.py            demo / train / replay modes
```

## Determinism rules

- Systems always run in the same fixed order.
- Systems visit entities in ascending ID order.
- No reads of wall-clock time inside systems.

## Risk to watch in the refactor

The hitbox size today comes from `pygame.transform.rotate` (the bounding box of the rotated image). A pure-math version could round differently and change behavior. **Resolved in step 2b:** `src/sim/geometry.py` `rotated_bounds` rotates a blank surface of the car's size, which needs no window and matches exactly. The polygon hitbox ([decision 004](004-polygon-hitbox-deferred.md)) will replace it. **Superseded in step 3d:** the polygon hitbox replaced `rotated_bounds`, which was then removed.

## Consequences

- Multi-car: create more car entities.
- Walls and other objects: new entities and components, with no changes to existing systems.
- Parallel envs: each process builds its own world with its own resources.
- More moving parts than a plain `World`/`Car` design, while there are still only two entity types.
