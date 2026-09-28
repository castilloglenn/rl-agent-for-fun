# 034: A camera for big stages: follow, fit, and a mini map

**Date:** 2026-09-28. **Status:** Accepted. Implemented in roadmap step 7b (`src/render/camera.py`, and the mini map in `renderer.py`).

## Context

The field view was the stage's exact size, so the window grew with the stage. A 1200 × 1200 map would need a window taller than most screens. First, the view grew up to 1100 × 640 and fitted a big stage into it; you preferred the box's view and the car's size kept on every stage, with a mini map.

## Decision

- **The field view is always the box's size, 855 × 480,** so the window and the car look the same on every stage. A stage that fits shows 1:1, exactly as before (a smaller one is centered): the box, `pillars`, and `s_curve` are pixel for pixel unchanged.
- **A bigger stage follows the car by default:** 1:1, centered on the car, stopping at the stage's edges (an axis where the stage fits stays centered).
- **F switches to fit,** the whole stage scaled into the same view (the arena at 40 %), an overview, and back. The DISPLAY card says which: `1:1`, `follow`, or `fit 40%`.
- **A mini map in follow mode,** inside the field at the top right, 150 px on its long side in the stage's shape: the walls, the checkpoint (green), the car (blue, with its heading), and an outline of the area the view shows, on a dark, nearly solid background with a 1 px outline. When the car drives under it, it moves to the top left, so it never hides the car. **M** hides or shows it. It isn't drawn in fit mode (the whole stage is on screen already) or on stages that fit.
- F and M are in every `?` shortcuts box.
- **Everything in the field goes through the camera:** the border, walls, checkpoints (at least 3 px), the car (rotated and scaled together in fit), its hitbox and rays, the trail, and the guide line. Drawing is clipped to the view, and a view onto a bigger stage gets a frame.
- **Clicks** print world coordinates, turned back through the camera (the map editor, 7c, builds on this).
- **Drawing only:** the simulation, replays, training, and headless runs never see the camera.
- **A sample stage, `arena`:** 1200 × 1200 (square, as you asked), with 7 walls.

## Consequences

- No setting for the view's size: it's the box's.
- Clicking the mini map to move the view (in replays) is a later idea on the roadmap.
