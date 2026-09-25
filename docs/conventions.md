# Conventions

## Geometry

- Angles are in degrees, in the range [0, 360).
- 0 points right, and positive turns counterclockwise on screen.
- Screen y grows downward, so `get_angular_movement_deltas` flips the sign of y (`src/utils/common.py`).
- 8 rays are angled relative to the car's heading (`RAY_LAYOUT` in `src/sim/systems/sensors.py`): 0, ±45, ±90, ±135, 180.
- Each ray starts on the car's body edge (`body_edge_distance`) and ends at the field border, with exact float distances (`distance_to_bounds`). Distance 0 means touching.

## Movement and physics

- The car's position is its **float center** (`Transform.x`, `Transform.y`), in world coordinates.
- The hitbox is the car's **4 real corners** (`car_corners` in `src/sim/geometry.py`), rotating with it. It never grows with the angle: see [decision 004](decisions/004-polygon-hitbox-deferred.md).
- **Border contact is exact:** a move goes as far as it can until a corner touches the border (`max_move_fraction`), then the car stops. A turn that would push a corner out is cancelled. Both become crashes in roadmap step 3f.
- The field's physics boundary is `Field.rect` (left/top edges included, right/bottom at `rect.right`/`rect.bottom`). The drawn border line sits exactly on it.
- `Motion.speed` is signed, in px per step along the heading: positive forward, negative reversing.
- `Motion.steering` is the wheel position, -1 (full right) to +1 (full left). A/D move it gradually (`next_steering`), and the turn rate follows it.
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
