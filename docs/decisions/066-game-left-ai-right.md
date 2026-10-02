# 066: The game on the left, the car and its AI on the right

**Date:** 2026-10-02. **Status:** Accepted. Built in roadmap 7f10 (`draw_game_panel` and `draw_car_panel` in `src/render/panels.py`, `src/render/instruments.py`, `Layout` in `src/render/layout.py`).

## Context

The side panels had grown feature by feature: the MIND card and the agent's reward sat on the left with the game, the map card on the right with the car, the checkpoint arrow and the waypoint were in two cards, and MIND's bars changed 30 times a second with uneven spacing. You asked for the AI side redesigned as a whole: game on the left, AI on the right.

## Decision

- **Left, the game:** the MAP card (big stages, moved from the right), DRIVER, GAME (stage, rules, spawns, seed), SCORE (distance, checkpoints, and Collected, moved from OBJECTIVE), LEADERBOARD (a replay: SOURCE), DISPLAY (FPS and vsync, camera and the sim rate, the shortcut hint; the step count went: the round timer says it).
- **Right, the car and its AI:**
  - **CAR**, the body: the speed bar and the steering slider, and the keys pressed beside its title (the agent's, or yours taking over). The heading dial and the position went: the radar faces the car's way, and the position was debugging.
  - **SENSES**, everything it perceives in one radar (it replaces SENSORS and OBJECTIVE): the 12 rays and the stopping arc, and on the rim the straight compass to the checkpoint (a green arrow) and the remembered waypoint (a violet diamond). Together they read at a glance: one direction, the way is clear; split, a wall is in between. Under it, the straight and route distances, and the stuck bar.
  - **MIND**, a fixed grid of the 12 actions (steering across, pedal down), each cell brighter the likelier, the picked one outlined, the ones a stopped car can't pick crossed out; and the outlook gauge. Both glide (smoothed over about 0.3 s, `Readouts.smooth`) instead of jumping with every decision. Shown when an agent drives.
  - **REWARD**, the old AGENT card: net, gains and costs on one line, the biggest cost.
- Display only: nothing in the simulation, the observation, or scores changes.

## Consequences

- Every column fits its tightest case: the box with MIND on the right, and an arena replay with a training replay's five SOURCE rows on the left.
