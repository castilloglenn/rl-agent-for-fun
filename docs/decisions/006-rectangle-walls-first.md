# 006: Rectangle walls first, angled walls later

**Date:** 2026-09-25. **Status:** Accepted, not implemented.

## Context

Maps (roadmap step 7) need walls, and the map editor (also step 7) needs to draw them. Walls can be axis-aligned rectangles or line segments at any angle.

| | Rectangles (axis-aligned) | Line segments (any angle) |
|---|---|---|
| Editing | Easiest: drag a box, snaps to a grid | Flexible: diagonal walls, curves from short segments |
| Rays | Easy: exact ray-to-rectangle distances, the same math as `distance_to_bounds` (step 3e) | New code: segment-to-segment intersection |
| Car collision | Simple checks against the polygon hitbox ([decision 004](004-polygon-hitbox-deferred.md), step 3d) | Needs SAT against the polygon hitbox |

## Decision

Start with axis-aligned rectangle walls, stored as `[x, y, width, height]` in map files. Add line segment walls later (roadmap step 8), alongside SAT collision.

## Consequences

- Step 3 reuses the existing ray and collision code.
- The map file format needs room for a second wall type later (for example a separate `segments` list), so old maps keep loading.
