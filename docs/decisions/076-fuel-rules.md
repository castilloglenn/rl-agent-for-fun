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
