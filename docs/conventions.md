# Conventions

## Geometry

- Angles are in degrees, in the range [0, 360).
- 0 points right, and positive turns counterclockwise on screen.
- Screen y grows downward, so `get_angular_movement_deltas` flips the sign of y (`src/utils/common.py`).
- Collision rays are angled relative to the car's heading: front 0, left +30, right -30, back 180.
- Rays start at an offset from the car center, and currently end where they hit the field border rect.

## Movement and physics

- The car's position is an integer pygame `Rect`. Float remainders build up in `x_float`/`y_float`, giving sub-pixel movement.
- The hitbox is currently the axis-aligned bounding box of the rotated image, so it grows when the car is angled. A polygon hitbox is planned but deferred: see [decision 004](decisions/004-polygon-hitbox-deferred.md).
- Reversing steers the other way: left input turns right while moving backward.
- Turn rate scales with the current acceleration.

## Determinism (must keep)

- The physics uses a **fixed timestep**. Per-frame speeds are `base_speed / fps`, and real elapsed time is not used.
- Never feed real elapsed time (for example `clock.tick()` results) into the physics. The clock belongs to `Renderer` only.
- Any future randomness (spawn position, maze layout) must be seeded.
- Replay depends on all of this: see [decision 003](decisions/003-replay-over-multi-window.md).

## Code style

- Max line length is 80 (`.flake8`).
- Commits follow conventional prefixes: `feat:`, `fix:`, `refactor:`, `chore:`.
