# 006: Rectangle walls first, angled walls later

**Date:** 2026-09-25. **Status:** Accepted, not implemented.

## Context

Maps (roadmap step 3) need walls, and the map editor (step 6) needs to draw them. Walls can be axis-aligned rectangles or line segments at any angle.

| | Rectangles (axis-aligned) | Line segments (any angle) |
|---|---|---|
| Editing | Easiest: drag a box, snaps to a grid | Flexible: diagonal walls, curves from short segments |
| Rays | Already work: rays use `Rect.clipline` | New code: segment-to-segment intersection |
| Car collision | Works with the current `Rect` hitbox | Needs the polygon hitbox ([decision 004](004-polygon-hitbox-deferred.md)) to be accurate |

## Decision

Start with axis-aligned rectangle walls, stored as `[x, y, width, height]` in map files. Add line segment walls in roadmap step 7, alongside the polygon hitbox.

## Consequences

- Step 3 reuses the existing ray and collision code.
- The map file format needs room for a second wall type later (for example a separate `segments` list), so old maps keep loading.
