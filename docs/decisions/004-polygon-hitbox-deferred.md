# 004: Polygon hitbox, deferred until after the refactor

**Date:** 2026-09-25. **Status:** Accepted, deferred.

## Context

The car's hitbox is a pygame `Rect`, which can't rotate. When the car turns, `Car._turn` uses the bounding box of the rotated image, which grows at 45°. That's fine against a border, but two cars would "collide" while visibly apart.

## Decision

Replace it with the car's 4 real corners as a polygon, checked with SAT (Separating Axis Theorem).

This changes where the car stops at borders, so it's a behavior change. It stays out of the refactor, and lands as its own step before multi-car (see [roadmap](../roadmap.md)).
