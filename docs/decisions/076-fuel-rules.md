# 076: Fuel rules: a tank, up to 3 fuels, out of fuel ends a car's round

**Date:** 2026-10-04. **Status:** Accepted. Built in roadmap 9a2 (`src/sim/rules.py` `Tank`, `src/sim/systems/tank.py`, `Tank` and `Refuel` in `components.py`, `FuelRules.at_once`, `spawning.py`, `factories.py`, `triggers.py`, the bars and the CAR panel, the rules and skill stage files). The numbers are starting values; 9a3 tunes them.

## Context

Step 9 replaces checkpoints with fuel (the plan in the roadmap, decision 075 for the name): one kind of target, a tank that makes every throttle and turn count, and rules fair enough for multiplayer (step 10).

## Decision

- **The tank, in the rules file** (`"tank"`, the same for every car): capacity 100, full at the start; it burns 1/s idle, +4/s with gas or reverse held, +1/s while turning, nothing for braking; a fuel puts back 40, up to the full tank. Rules without `"tank"` burn nothing (fuel then only scores).
- **Empty:** the engine is dead. The tank system runs first each step and clears the controls, so the car coasts (its drag slows it); once it has stopped it's out ("out_of_fuel", through `eliminate`), and the round ends when every car is out, as for wrecks. Coasting into a fuel refills the tank and the engine runs again. The env's episode ends there (`terminated`, `ended_by` "out_of_fuel").
- **Up to 3 fuels at once** (`FuelRules.at_once`, 1 to 3, default 3). Scripted, the spawn schedule already hands out the next point in order, so 3 fuels start at points 1 to 3 and taking any brings in point 4: a sliding window; never more than the stage's points. Random: 3 random ones, each clear of the cars and of the other fuels (the stage's `min_car_distance`). The `skill_` test maps say 1, so their tests stay what they test.
- **The spawner is called "fuel" now** (its random stream's name, kept "checkpoints" through 9a1): random fuels sit elsewhere than before.
- **No distance points:** `scoring.distance_step` 0 in every built-in rules file (0 now means none). Game points come from fuel only (+100 each); they'd otherwise pay for driving around in multiplayer.
- **Seeing it:** a fuel bar under the health bar above the car (blue, amber from 30 %, red under 15 %; hidden when full if your bars show only when damaged), and a Fuel row in the CAR panel. The SCORE card leaves out Distance when the rules have none.

## Consequences

- The behavior fixtures were regenerated: the car's physics matched step for step; only the score changed (no distance points).
- Agents don't sense the tank yet (9b), and the reward doesn't charge for fuel yet (9c).
- The heuristic on the box took 7 fuels in 12 s and kept its tank above 90 %, so the starting numbers may be too generous: 9a3 measures and tunes.

**Tuned (9a3, 2026-10-04):** steering burns +1.5/s (was 1) and a fuel puts back 25 (was 40); capacity 100, idle 1/s, and throttle +4/s stay. The target: the navigator (a good driver) never runs dry on the training maps, the heuristic sometimes does, and a random driver runs dry in about 20 s. Measured on 9 training maps, 4 rounds each, the navigator ran dry 0 of 36 rounds (its tank 88 % on average, under half 5 % of the time; 91 % and 2 % before), the heuristic 11 of 36 (8 before), and a random driver everywhere, at about 26 s (a smaller tank would get nearer 20 s, but would also hurt the first drive from the spawn). Tighter versions made the navigator run dry: steering +2/s with a refill of 25, 4 of 36 (course_large 3, route_switchbacks 1); with a refill of 15, 6 of 36. With 3 fuels near, a good driver takes one every 2 s or so and stays nearly full, so the tank mostly punishes slow or aimless driving and long trips, not good drivers on open maps: being better keeps you alive. One known gap: on `route_switchbacks` (random fuels in a maze) the navigator ran dry 1 round in 6, before the tuning too: it chases the fuel nearest in a straight line (9b chooses by route).

**`route_spiral` gets fuels along its route (9a3):** it had 2 points 4,614 px apart by road, 25 to 30 s of driving, while a full tank lasts 17 to 20 s; the navigator ran dry there 6 times of 6, even with 1 fuel at a time. Now 16 points, about every 600 px along the padded route (33 px or more from any wall): inward to the center, then outward offset by 300 px (no spot twice), then the corner. The navigator lasts the 60 s there and takes 19 fuels; the heuristic, which can't follow a route, still runs dry.

**Distance points back (9a4, 2026-10-05):** without them a game score was only fuel, in hundreds (a few fuels a round), so you asked for points for moving again, in the game score only: +1 per 10 px driven forward, as before 9a2 (`distance_step` 10 in the built-in rules). The agent's reward never used game points, so nothing it learns changes. Typical scores now: the navigator 4,676 on the box (976 from driving, 3,700 from fuel), 3,625 on the arena, 3,062 on `course_large`; the heuristic 3,085, 1,756, 694. Fuel still outweighs driving for a good driver (about 3 to 1), and driving around without taking fuel burns the tank, so it can't pay for long.

