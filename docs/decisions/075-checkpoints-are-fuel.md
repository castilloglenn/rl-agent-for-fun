# 075: The game's checkpoints are called fuel

**Date:** 2026-10-04. **Status:** Accepted. Built in roadmap 9a1 (91 files: the simulation, the env, the drivers, the editor, the renderer, the control center, the stage, rules, and reward files, the tests, and the docs that describe the game now).

## Context

Step 9 makes the checkpoints fuel: up to 3 on the map, refilling a tank that every throttle and turn burns (the step 9 plan in the roadmap). You chose to call them fuel everywhere, and to do it while no agents or recordings exist, so nothing old has to keep working.

## Decision

- **A refactor only:** the rename changes no behavior. 12 heuristic rounds on 6 maps (the box, the arena, both courses, `route_rooms`, `skill_detour`) gave the same score, fuels taken, agent reward, final position, and final observation before and after, and the behavior fixtures still pass.
- **The names:** a fuel is one target, and counts are "fuels": `Fuel` (the tag), `FuelRules` and `Stage.fuel` (a stage's `"fuel": {...}`), `scoring.fuel` (points per fuel), the `fuels` and `fuel_speed` reward terms, `Score.fuels` and `fuel_points`, `EpisodeResult.fuels`, `fuels_per_min` in the suite results, the observation's `fuel_distance`, `fuel_sin`, `fuel_cos`, `theme.FUEL`, `hud.fuel_near`, and the editor's fuel tool.
- **Saved weights stay "checkpoints":** an agent's `checkpoints/d0100k.pt`, the best checkpoint, branching from one. That's the usual machine-learning word, and a different thing.
- **Kept until 9a2:** the spawner's name `"checkpoints"`, because it seeds its random stream: renamed now, every random fuel would move. 9a2 changes the spawning anyway, and renames it. The editor's key for the fuel tool stays C.
- **History stays as written:** older decisions and roadmap rows keep "checkpoint", as it was then.

## Consequences

- Stage files say `"fuel"`, rules `"scoring": {"fuel": 100}`, and the default reward `"fuels": 500`. A stage of yours made before would need its key renamed (none exist).
- `metrics.csv` has a `fuels` column, and the Runs tab's chart is "Fuels".
