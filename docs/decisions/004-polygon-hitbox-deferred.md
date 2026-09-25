# 004: Polygon hitbox, after the refactor (roadmap step 3d)

**Date:** 2026-09-25. **Status:** Accepted, scheduled for roadmap step 3d (moved up from the multi-car step).

## Context

The car's hitbox is a pygame `Rect`, which can't rotate. When the car turns, `steering_system` uses the bounding box of the rotated image (`rotated_bounds`), which grows at 45°. That's fine against a border, but two cars would "collide" while visibly apart.

## Decision

Replace it with the car's 4 real corners as a polygon, checked with SAT (Separating Axis Theorem).

This changes where the car stops at borders, so it's a behavior change. It stayed out of the refactor (step 2).

## Update: moved to step 3d

Crash = game over (step 3f) makes the growing box unacceptable: a diagonal car would crash while visibly pixels away from the border, which is unfair to human drivers and teaches agents the wrong margins. So the polygon lands in step 3d, before crashes:

- Position becomes a float center point, and the hitbox is the 4 rotated corners.
- In the box map, a corner check against the field is exact.
- SAT comes later with inner walls (step 7) and car-vs-car collision (step 8). See [roadmap](../roadmap.md).
