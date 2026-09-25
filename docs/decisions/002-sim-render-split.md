# 002: Split simulation from rendering, remove global state

**Date:** 2026-09-25. **Status:** Accepted, not implemented.

## Context

All planned features run into two problems in the current code:

1. Global singletons (`StateSingleton`, `FieldSingleton`, and `FLAGS` read everywhere) allow only one car and one env per process.
2. Sprites both simulate and draw, so there's no fast headless simulation separate from the view.

## Decision

Target layout:

```
sim/        World: walls + list of cars, step(actions) -> new state
            Pure Python/math, no pygame drawing, no globals, config passed in
env/        MazeCarEnv: wraps a World, builds observations, reward, done
            Gymnasium-style API: reset(seed) / step(action)
render/     Renderer: draws a World with pygame, optional
replay/     Recorder (JSON Lines) + Replayer
agents/     Learning agent (torch), talks only to env/
app.py      Wires modes: demo / train / replay
```

- `Car` is an object that knows only about itself: it applies an action and reports its hitbox.
- Collisions belong to `World`, because they involve two objects. Each `World.step` runs three phases: move all cars, detect collisions, resolve them. Moving everyone first keeps the result independent of car order.
- Rays are cast by `World` against walls, and later against other cars.

## Consequences

- Multi-car: `World` holds a list of cars.
- Parallel envs: each process builds its own `World`.
- Replay and training use the same deterministic `World.step`.
- The renderer only reads the world, so switching it on or off doesn't change results.
