# 062: Seeing what the agent senses and thinks

**Date:** 2026-10-01. **Status:** Accepted. Built in roadmap 7f8 (`_draw_route` and `_draw_stuck_ring` in `src/render/renderer.py`, the MIND card and the Stuck row in `src/render/panels.py`, `route_points` in `src/sim/route.py`, `AgentDriver`'s latest decision).

## Context

7f7 gave agents a remembered route waypoint and a stuck timer, and you wanted to see everything the agent senses and thinks, in live watching and in replays: covering the map and looking only at the sensors showed how blind it is.

## Decision

- **On the field, with the lines (H):**
  - the remembered **waypoint** as a violet diamond with a dashed line from the car, and a ring that pulses for 0.4 s when it's refreshed (reached, or every 2 s);
  - the **rest of the remembered route**, faint dots from the waypoint on to the checkpoint (a new display setting, "Full route, faint", on by default). It's drawn from the waypoint, not from the car: in a symmetric U the shortest way around can flip as the car moves, and a route drawn from the car would disagree with the waypoint the agent holds. The agent never sees these dots, only the waypoint;
- **Being stuck shows in the side panel only:** a Stuck row (a bar and the seconds, amber, red from 5 s) in OBJECTIVE. A ring around the car that filled as the timer grew was built first and removed at your request: one place is enough; the DISPLAY card shows the camera and vsync on one line to make room.
- **A MIND card** when an agent drives (watching live, the showcase, and replays that name an exact checkpoint that still exists; training replays came from changing weights, so they have none): its next move's odds as two split bars (steering: left, straight, right; pedal: gas, coast, brake, reverse; the most likely of each named), and its **outlook** (the value head: how good it thinks the situation is) as a gauge from the middle, scaled to the largest value seen. Stopped, the title says "stopped: gas or reverse" (7f6). It takes the place of the one-car leaderboard.
- Display only: the simulation, the observation, and scores don't change. The agent driver now keeps its latest decision's probabilities and value (sampling and greedy picks unchanged).

## Consequences

- A raw view of all 23 inputs is left for later, if this isn't enough.
