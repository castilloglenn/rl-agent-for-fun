# 059: Twelve rays, and instruments instead of changing numbers

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7f3 (`RAY_LAYOUT` in `src/sim/systems/sensors.py`, `src/render/instruments.py`, `draw_car_panel` in `src/render/panels.py`).

## Context

With 8 rays 45 degrees apart, something narrow can sit between two rays until the car is close: a 48 px gap (hard `course_small`) shows only from 63 px away, a 30 px pillar from 39 px, closer than the 75 px the car needs to brake from full speed. agent_2 was weak at Obstacles and Threading. There were no agents left, so changing what agents see cost nothing. Separately, the side panel's numbers (speed, steering, heading, 8 ray distances, the checkpoint) changed every frame, too fast to read; with 12 rays it would be worse.

## Decision

- **12 rays, denser in front:** 0, ±15, ±30, ±45, ±90, ±135, and 180 degrees (the new ones `front_left_15`, `front_left_30`, `front_right_30`, `front_right_15`), in order around the car. A 48 px gap now shows from 184 px, a 30 px pillar from 115 px. The 8 rays kept their names and angles, so the heuristic (which reads `front`, `front_left`, `front_right`) drives and scores the same. The observation grows from 15 to 19 numbers.
- **The observation stays version 1** (the first-version rule, with no agents): recordings stay usable for imitation, since datasets rebuild observations by replaying them with the current sensors. The behavior fixtures were regenerated: the only change is the 4 added rays, every other value the same.
- **The side panel shows instruments:**
  - **CAR:** speed as a bar (zero a quarter in; forward fills right, colored by how safe the speed is; reversing fills left in red), steering as a slider (the dot left of center turns left), heading as a dial, and position; the pedal row went (the lit keys show it).
  - **SENSORS:** a radar, the car facing up with a spoke per ray at its angle, as long as the way is clear up to 300 px, colored by danger (gray when nothing is near), the stopping distance as an arc in the direction of travel (it replaces the "Stop dist" row: a wall inside the arc can't be avoided by braking), and the closest wall in one line.
  - **OBJECTIVE:** an arrow toward the checkpoint relative to the car, and a bar for its distance.
- **Steady numbers:** each number left shows its mean over the last quarter second and is redrawn 4 times a second (`Readouts`; an angle holds its latest value instead of a mean). Display only: the simulation, the observation, and replays don't change.
- The side panels may draw simple shapes now (an earlier rule kept them to lines and text).

## Consequences

- Agents trained before have 15 inputs and won't load (none exist).
- The rays take about a fifth of the simulation's time; 4 more add roughly 10 %.
