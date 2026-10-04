# 077: The agent senses its tank and the 3 fuels, nearest by route first

**Date:** 2026-10-05. **Status:** Accepted. Built in roadmap 9b (`src/sim/observation.py`, `src/sim/route.py`, the heuristic and the navigator, the SENSES radar and the guide line, `guard.INPUTS`).

## Context

Since 9a2 up to 3 fuels are out and a tank burns, but an agent saw one fuel (the nearest in a straight line) and no tank. Step 9's plan: its fuel level, and the 3 fuels nearest by route, each with the straight compass and the route sensor (7f7).

## Decision

- **39 inputs** (version 1 kept: agents start from scratch): the 12 rays, speed, steering, the **tank** (1 full .. 0 empty; 1 without a tank), then **3 fuel slots**, then stuck, time left, and health. A slot: present, straight distance, sin, cos, route distance, route sin, route cos. An empty slot reads present 0, far, and no direction (as "no fuel" read before).
- **A route per fuel:** the route sense keeps a `FuelRoute` for each fuel out, each with its own remembered waypoint refreshed as before (reached, passed, or every 2 s). The slots are ordered by each route's distance **now** (computed every step anyway): ordered by the remembered distances, refreshed at different times, "nearest" flipped between fuels and the navigator zigzagged (on the box: 25.5 fuels a round and 2 of 6 dry, against 39.5 and none). The first slot only changes when another fuel is more than 40 px nearer, so two about as far don't swap every step. The route distance input is the distance now too, so the order and the numbers agree.
- **The stuck timer** counts toward the nearest fuel by route, and starts over when a fuel is taken.
- **The drivers:** the heuristic (the 1.0 bar) keeps its rule: of the fuels out, the nearest in a straight line. The navigator follows the first slot's route.
- **The window:** the SENSES radar's compass and waypoint, its distances, and the guide line follow the nearest fuel by route (the guide line went to every fuel since 9a2).

## Consequences

- The navigator on 10 training maps: about the same as when it chased the nearest in a straight line. A direct comparison, 12 rounds each on the arena, `pillars`, and `route_rooms`: 25.4 / 28.1 / 16.5 fuels a round by route, 24.3 / 28.8 / 15.9 in a straight line, no round dry either way, 4 wrecks against 2 (its own driving, under either). `route_switchbacks` still runs dry 1 round in 6.
- The agent's reward still pays progress toward the nearest fuel in a straight line: 9c moves it to the nearest by route and adds the fuel terms.
