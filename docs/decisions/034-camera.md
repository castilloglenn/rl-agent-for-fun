# 034: A camera for big stages: fit or follow

**Date:** 2026-09-28. **Status:** Accepted. Implemented in roadmap step 7b (`src/render/camera.py`).

## Context

The field view was the stage's exact size, so the window grew with the stage. A 1200 × 1200 map would need a window taller than most screens.

## Decision

- **A field view between 855 × 480 and 1100 × 640** (`window.max_field`, a display setting). A stage that fits shows 1:1, exactly as before: the box, `pillars`, and `s_curve` are pixel for pixel unchanged.
- **The view never goes below 855 × 480** (the box's size): the top bar above it needs that width. A narrower stage (after fitting) is centered in the view.
- **Two modes for a bigger stage, F switches:** **fit** (the default), the whole stage scaled down; and **follow**, 1:1 and centered on the car, stopping at the stage's edges (an axis where the stage fits stays centered). The DISPLAY card says which: `1:1`, `fit 53%`, or `follow`. F is in every `?` shortcuts box.
- **Everything in the field goes through the camera:** the border, walls, checkpoints (at least 3 px), the car (rotated and scaled together, smoothly), its hitbox and rays, the trail, and the guide line. Lines stay 1 px. Drawing is clipped to the view, and a view onto a bigger stage gets a frame.
- **Clicks** still print world coordinates, turned back through the camera (the map editor, 7c, builds on this).
- **Drawing only:** the simulation, replays, training, and headless runs never see the camera.
- **A sample stage, `arena`:** 1200 × 1200 (square, as you asked), with 7 walls. It fits at 53 %.

## Consequences

- On a big stage in fit mode the car is small (about 13 × 9 px for the arena): follow mode is the one for driving.
- The window for the arena is 1429 × 732 (the box's width, 160 px taller).
