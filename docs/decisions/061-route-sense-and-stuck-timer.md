# 061: A sense of direction (a remembered route) and a stuck timer

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7f7 (`src/sim/route.py`, `src/sim/observation.py`, `src/envs/maze_car/env.py`).

## Context

With a wall between the car and the checkpoint, agents pushed into the wall until time ran out. They see 12 wall distances and a compass pointing in a straight line through the wall; nothing says which way around is shorter, or that they've been stuck for a while, and they have no memory. You see the whole map. A driver without GPS still has a sense of "the way around is over there", and notices being stuck.

## Decision

- **A remembered waypoint:** along the shortest drivable route to the checkpoint (the route field the progress reward already uses, one per checkpoint, since walls don't move), the last point still in a straight line from the car with 10 px to spare from walls: about one corner ahead (the checkpoint itself when in sight). It's held, and refreshed when the car comes within 30 px of it or every 2 s (not 5: at full speed the car covers 1,500 px in 5 s, enough to drift far off a stale route). Between refreshes the car sees the waypoint's direction relative to its own heading, every step, so turning the car doesn't make it point wrong.
- **The remembered route distance,** refreshed with the waypoint.
- **A stuck timer:** seconds since the car last got 10 px closer along the route than it had been to this checkpoint, read as 0 to 1 over 10 s.
- **The observation grows from 19 to 23 numbers** (`route_distance`, `route_sin`, `route_cos`, `stuck`, after the checkpoint compass). The straight compass stays. The heuristic doesn't use them, so it stays the 1.0 bar, and agents can now pass it in mazes.
- **It's general for any target:** fuel (step 9) gets the same sensor per fuel slot, and the agent learns from the reward which comes first. The route knows only the map's walls; other cars (step 10) are for the rays, so it never needs updating for them.
- **Where:** a `RouteSense` component on the car, updated when the observation is built (once a step); a plain simulation never pays for it, and the behavior fixtures don't change. One route-field cache (`RouteFields`, in the world) serves both this sense and the progress reward, so training computes nothing more than before.

## Consequences

- Scoring a checkpoint on the suite takes about 17 % longer (the heuristic on the whole suite: 5.0 s, now 5.8 s): the evaluation plays for game points, so it built no route fields before.
- Agents trained before have 19 inputs and won't load (none exist).

**Fix (2026-10-02):** the walk that traces the route (for the waypoint and the faint dots) could step through a thin wall: next to one, a point on its far side reads the far side's shorter distance. Seen on `route_spiral`, where the dots cut across its corner. Each step now keeps 6 px clear of every wall (a test checks it on the spiral). The route field itself, the route distance, and the progress reward were never affected.

**Padding (2026-10-02):** the waypoint and the drawn route now follow a padded route field that keeps 30 px from walls (the exact one keeps 8, half the car's width, and hugged every corner, so drivers aimed at corner tips). Where padding closes the way, or makes the route more than 10 % (and 60 px) longer, the exact route is used: `skill_gaps`' 40 px gaps and hard `course_small`'s 48 px gaps. The route distance and the progress reward stay on the exact field. The navigator measured the same or better (`course_large` 20.0 → 22.7 checkpoints a minute); a stricter sight line (16 px instead of 10) was tried at the same time and reverted: in a 40 to 48 px gap it stopped the waypoint short of the gap (`skill_gaps`: 6 wrecks in 6 rounds).

**Overshoot (7f15, 2026-10-02):** the waypoint was held until the car came within 30 px of it (or 2 s passed); a car sweeping past it wider than that turned back to collect it. Now it's also refreshed the moment the car is closer to the checkpoint along the route than the waypoint is (it's behind), and the reach is 45 px. The navigator measured the same (`course_large` 23.2 checkpoints a minute, `course_small` 20.5).

**Faster, the same route (7f16, 2026-10-02):** each step of the walk and each sight line checked every wall of the map; now they check only the walls near enough to matter (a point 12 px from the step's start is at most 12 px nearer any wall), so the waypoints and the drawn route are the same, checked on 3,369 samples over five maps. The waypoint takes 3 to 7 times less time (`route_spiral`: 6.8 s to 2.1 s over three rounds). An env also keeps its route fields across its games (by map, walls, goal, and clearance; the 64 used most recently), so a course's scripted checkpoints are built once: about 10 % faster rounds on `course_large`, little elsewhere. Tried first and dropped: following the grid's own links from cell to cell instead of the walk. It was faster still, but those links move only straight or at 45 degrees, so the last one in sight zigzagged off the shortest line and the navigator got stuck more (`route_rooms`: stuck 9 % to 19 % of the time).
