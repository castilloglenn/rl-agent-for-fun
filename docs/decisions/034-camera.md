# 034: A camera for big stages: follow, fit, and a map card

**Date:** 2026-09-28. **Status:** Accepted. Implemented in roadmap step 7b (`src/render/camera.py`, and the map card in `renderer.py` and `layout.py`).

## Context

The field view was the stage's exact size, so the window grew with the stage. A 1200 × 1200 map would need a window taller than most screens. First, the view grew up to 1100 × 640 and fitted a big stage into it; you preferred the box's view and the car's size kept on every stage, with a mini map. The mini map started inside the field and moved out of the car's way; that was dizzying, so it became a fixed card.

## Decision

- **The field view is always the box's size, 855 × 480,** so the window and the car look the same on every stage. A stage that fits shows 1:1, exactly as before (a smaller one is centered): the box, `pillars`, and `s_curve` are pixel for pixel unchanged.
- **A bigger stage follows the car by default:** 1:1, centered on the car, stopping at the stage's edges (an axis where the stage fits stays centered).
- **F switches to fit,** the whole stage scaled into the same view (the arena at 40 %), an overview, and back. The DISPLAY card says which: `1:1`, `follow`, or `fit 40%`.
- **A MAP card, fixed at the top of the right column** (on stages bigger than the view only): the whole stage, 200 px on its long side in the stage's shape, with the walls, the checkpoint (green), the car (blue, with its heading), and in follow mode an outline of the area the view shows. The right column's cards stack under it.
- **The window grows as tall as the card** (the arena: 1429 × 836), and so does the field view (855 × 744), so it shows more of a big stage at 1:1. The box and the other stages that fit keep their exact window.
- **A map intro at the start of each round** on a big stage: the whole map (fit) for 3 s with a hint ("The whole map · any key skips"), then a smooth 1 s zoom into follow mode (eased at both ends). The DISPLAY card says `overview` meanwhile. It's real time and drawing only: the simulation doesn't wait (in replays and watched agents the car may already move). Any key skips it, so in live play your first driving key goes straight to the game; F during it keeps the overview. It starts on every new round (a restart too), and in the showcase when the title card closes. `window.map_intro` (default on) turns it off.
- F is in every `?` shortcuts box.
- **Everything in the field goes through the camera:** the border, walls, checkpoints (at least 3 px), the car (rotated and scaled together in fit), its hitbox and rays, the trail, and the guide line. Drawing is clipped to the view, and a view onto a bigger stage gets a frame.
- **Clicks** print world coordinates, turned back through the camera (the map editor, 7c, builds on this).
- **Drawing only:** the simulation, replays, training, and headless runs never see the camera.
- **A sample stage, `arena`:** 1200 × 1200 (square, as you asked), with 7 walls.

## Consequences

- No setting for the view's size: it's the box's (plus the map card's height on a big stage).
- Clicking the mini map to move the view (in replays) is a later idea on the roadmap.
