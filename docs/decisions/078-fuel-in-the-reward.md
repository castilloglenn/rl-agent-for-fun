# 078: Fuel in the agent's reward

**Date:** 2026-10-05. **Status:** Accepted. Built in roadmap 9c (`src/envs/maze_car/rewards.py`, `env.py`, `rewards/default.json`).

## Context

Since 9a2 a tank burns and running dry ends a car's round, and since 9b the agent senses its tank and the 3 fuels, nearest by route first. The reward still paid progress toward the nearest fuel in a straight line, didn't charge for fuel, and counted running dry as a wreck: the `wrecked` term fired on any way out of the round.

## Decision

- **Progress toward the nearest fuel by route** (the first fuel it senses), measured toward the same fuel before and after each step, so a new nearest is no jump.
- **`fuel_burned`: -5 per unit** of fuel burned (idle, throttle, steering, by the rules' tank). A full tank costs about one fuel (-500), so every throttle and turn counts, without making standing still pay: idling burns too, and stopping costs as before.
- **`out_of_fuel`: -3000**, like a wreck: the round ends early, and every fuel it could still have taken is lost.
- **`wrecked` is wrecks only** now (health reaching 0), apart from running dry.
- The rest stays: +500 per fuel, contacts, damage, stopped, stuck (toward the nearest fuel since 9b).

## Consequences

- Measured on the arena, `course_large`, and `route_rooms` (3 rounds each), the mean per round: the navigator +21,503 (progress +11,526, fuels +11,778, fuel burned -1,516), the heuristic +8,897 (fuel burned -1,301, out of fuel -667), a random driver -4,320 (fuel burned -500, out of fuel -3,000). Burning fuel costs a good driver about 7 % of what it earns: a steady nudge to drive efficiently, not a brake on driving.
- Recordings made before 9c are gone (deleted for 9a1); the navigator is recorded again from scratch for cloning (9e).
