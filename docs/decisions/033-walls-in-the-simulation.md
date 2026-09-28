# 033: Walls inside the field

**Date:** 2026-09-28. **Status:** Accepted. Implemented in roadmap step 7a (`src/sim/walls.py`, and the movement, steering, sensor, and spawning code).

## Context

Stage files had room for walls since step 4b (`"walls": []`), and [decision 006](006-rectangle-walls-first.md) chose axis-aligned rectangles first. The border was the only thing a car could hit. Step 7a makes walls real: the same physics as the border, so everything learned about hits, damage, and sliding carries over.

## Decision

- **Format unchanged:** `"walls": [[x, y, width, height], …]` in the stage file. Validation adds: walls inside the stage with a positive size, the spawn at least 16 px from every wall (a car is 24 × 16: 14.4 px from its center to a corner), and scripted checkpoints not touching a wall.
- **A `Walls` resource** (static rectangles) next to `Field`, built from the stage. The roadmap said wall entities; a resource is simpler and faster for walls that never move. Entities can come with moving hazards.
- **Two kinds of contact** (the hitbox is a rotated rectangle): a car corner entering a wall's face, or a wall corner entering the car's side. The move stops at the first one; its contact normal points out of the wall.
- **The border's rules, generalized:** impact speed = the speed along the normal, damage by the rules, the slide keeps the motion along the surface (a slanted surface when a wall corner meets the car's side), and scraping costs health per px. A slide blocked again (into a corner) stops the car. The border keeps its exact x/y arithmetic, so the box stage is bit-identical: the behavior fixtures pass unchanged.
- **Touching isn't inside:** a point within 1e-6 px of a surface is on it, so a car resting against a wall can slide along it or drive away, without sticking or passing through (a stress run: 345,600 steps of random and heuristic driving on the wall stages, never overlapping).
- **Turning** into a wall is blocked with an impact (the fastest corner that would enter), like turning into the border.
- **Rays** stop at the nearest wall or the border. The observation is unchanged (8 rays); agents simply start seeing walls. The sensor card now reads "px to a wall".
- **Checkpoints** skip random spots closer to a wall than the border margin (40 px). The first 8 candidates of a slot are drawn exactly as before (no walls: nothing changes); more are drawn only when walls reject all of them.
- **Drawn** as dark filled rectangles with the border's outline.
- **Sample stages:** `pillars` (4 blocks, random checkpoints) and `s_curve` (two walls making an S, scripted checkpoints that lead through it). Both are the box's size.

## Consequences

- Replays embed the whole stage, walls included, and verify on wall stages.
- Agents trained on the box have never seen walls: expect them to hit these (step 7d brings map skills to the suite).
- Each step checks every wall; fine for tens of walls. A grid lookup can come if maps get big.
