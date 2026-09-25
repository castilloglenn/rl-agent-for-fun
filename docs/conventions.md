# Conventions

## Geometry

- Angles are in degrees, in the range [0, 360).
- 0 points right, and positive turns counterclockwise on screen.
- Screen y grows downward, so `get_angular_movement_deltas` flips the sign of y (`src/utils/common.py`).
- Collision rays are angled relative to the car's heading: front 0, left +30, right -30, back 180.
- Rays start at an offset from the car center, and currently end where they hit the field border rect.

## Movement and physics

- The car's position is an integer pygame `Rect`. Float remainders build up in `x_float`/`y_float`, giving sub-pixel movement.
- The hitbox is currently the axis-aligned bounding box of the rotated image, so it grows when the car is angled. It's replaced by the car's real 4 corners in roadmap step 3d: see [decision 004](decisions/004-polygon-hitbox-deferred.md).
- `Motion.speed` is signed, in px per step along the heading: positive forward, negative reversing.
- Steering flips while the car actually rolls backward (based on the speed's sign, not the pressed keys).
- Turn rate follows speed, and is 0 at a stop. Driving rules: [game design](game-design.md#controls-realistic-driving).

## Determinism (must keep)

- The physics uses a **fixed timestep**: `sim.steps_per_second` (120), independent of the display. Config speeds and accelerations (px/s, px/s²) are converted to per-step units by dividing by the step rate (and its square for accelerations).
- Real elapsed time only decides **how many** steps the demo runs per frame (`FixedStepClock`), never **what** a step does. Never feed it into a system.
- Any future randomness (spawn position, maze layout) must be seeded.
- Replay depends on all of this: see [decision 003](decisions/003-replay-over-multi-window.md).

## Code style

- Max line length is 80 (`.flake8`).
- Commits follow conventional prefixes: `feat:`, `fix:`, `refactor:`, `chore:`.
