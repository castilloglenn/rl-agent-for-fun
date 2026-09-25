# 008: Fixed-timestep simulation at 120 steps/s, drawing at the display rate

**Date:** 2026-09-25. **Status:** Accepted, roadmap step 3c.

## Context

The simulation ran one step per drawn frame at 90 FPS. On displays that refresh at 60 or 120 Hz, 90 FPS doesn't divide evenly, so frames stay on screen for uneven times, which feels like stutter. Measured: simulation plus all drawing costs 0.38 ms per frame, so the workload wasn't the problem.

Letting the frame rate follow the display would change the physics per machine, because step sizes came from the FPS. That breaks determinism (replays, agents trained elsewhere).

## Decision

Separate the two clocks:

| Clock | Rate | Role |
|---|---|---|
| Simulation | Fixed **120 steps/s** (`sim.steps_per_second`) | Physics, timer, rewards. Identical everywhere, including headless |
| Drawing | Auto-detected display refresh rate, with vsync where available. `display.max_fps` overrides it | Smooth screen updates |

Each drawn frame:

1. Adds the real time elapsed to an accumulator, then runs as many fixed steps as fit (usually 0, 1, or 2). Real time only decides **how many** steps run, never **what** a step does.
2. Draws each car **interpolated** between its previous and current step pose, so motion looks smooth even when a frame falls between steps.

### Why 120 steps/s

At the top speed of 600 px/s, a car moves per step:

| Rate | Per step | Notes |
|---|---|---|
| 60 | 10 px | Coarse: head-on cars (16 px wide) close 20 px per step and could skip past each other |
| 90 | 6.7 px | Fine for the box map |
| **120** | **5 px** | Precise enough for thin walls and car-vs-car collision |
| 180 | 3.3 px | Diminishing returns, with longer step counts and replays |

Compute doesn't decide it: one step costs about 7 µs (151,000 steps/s measured).

Update: the top speed was later calibrated down to 300 px/s for human play, so per-step movement is now half the values above (2.5 px at 120 steps/s). 120 still leaves headroom if faster cars come back.

### Agent action repeat: 30 decisions/s

Agents decide every **4 steps** and hold the action in between. A 60 s round is then 1,800 decisions instead of 7,200, which keeps learning manageable. Built in roadmap step 5.

## Consequences

- Switching 90 → 120 changes the per-step physics, so the behavior fixtures are regenerated. Driving feel in seconds is unchanged, because config values are in px/s and px/s².
- Round timer: 60 s = 7,200 steps.
- Durations in steps scale with the rate: 2 s = 240 steps.
- The frame loop (demo) and the renderer handle real time. The simulation never sees it.
