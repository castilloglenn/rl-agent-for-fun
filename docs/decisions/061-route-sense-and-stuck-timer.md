# 061: A sense of direction (a remembered route) and a stuck timer

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7f7 (`src/sim/route.py`, `src/sim/observation.py`, `src/envs/maze_car/env.py`).

## Context

With a wall between the car and the checkpoint, agents pushed into the wall until time ran out. They see 12 wall distances and a compass pointing in a straight line through the wall; nothing says which way around is shorter, or that they've been stuck for a while, and they have no memory. You see the whole map. A driver without GPS still has a sense of "the way around is over there", and notices being stuck.

## Decision

- **A remembered waypoint:** along the shortest drivable route to the checkpoint (the route field the progress reward already uses, one per checkpoint, since walls don't move), the last point still in a straight line from the car with 10 px to spare from walls: about one corner ahead (the checkpoint itself when in sight). It's held, and refreshed when the car comes within 30 px of it or every 2 s (not 5: at full speed the car covers 1,500 px in 5 s, enough to drift far off a stale route). Between refreshes the car sees the waypoint's direction relative to its own heading, every step, so turning the car doesn't make it point wrong.
- **The remembered route distance,** refreshed with the waypoint.
- **A stuck timer:** seconds since the car last got 10 px closer along the route than it had been to this checkpoint, read as 0 to 1 over 10 s.
- **The observation grows from 19 to 23 numbers** (`route_distance`, `route_sin`, `route_cos`, `stuck`, after the checkpoint compass). The straight compass stays. The heuristic doesn't use them, so it stays the 1.0 bar, and agents can now pass it in mazes.
- **It's general for any target:** fuel (step 9) gets the same sensor per fuel slot, and the agent learns from the reward which comes first. The route knows only the map's walls; other cars (step 8) are for the rays, so it never needs updating for them.
- **Where:** a `RouteSense` component on the car, updated when the observation is built (once a step); a plain simulation never pays for it, and the behavior fixtures don't change. One route-field cache (`RouteFields`, in the world) serves both this sense and the progress reward, so training computes nothing more than before.

## Consequences

- Scoring a checkpoint on the suite takes about 17 % longer (the heuristic on the whole suite: 5.0 s, now 5.8 s): the evaluation plays for game points, so it built no route fields before.
- Agents trained before have 19 inputs and won't load (none exist).

**Fix (2026-10-02):** the walk that traces the route (for the waypoint and the faint dots) could step through a thin wall: next to one, a point on its far side reads the far side's shorter distance. Seen on `route_spiral`, where the dots cut across its corner. Each step now keeps 6 px clear of every wall (a test checks it on the spiral). The route field itself, the route distance, and the progress reward were never affected.
