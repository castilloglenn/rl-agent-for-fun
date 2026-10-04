# 079: Economy, a fuel skill in the suite

**Date:** 2026-10-05. **Status:** Accepted. Built in roadmap 9d (`stages/skill_fuel.json`, `suites/skills.json`).

## Context

Step 9 plans the skills suite on fuel: the test maps keep one fuel at a time (done in 9a2, so their tests stay what they test) and a skill only fuel makes possible. In "Long range" (far fuels, 25 s rounds) a full tank, about 16 to 20 s of driving, barely matters.

## Decision

- **Economy** (group Fuel): `skill_fuel`, an open 1600 x 1200 map, one fuel at a time at least 750 px from the car, 45 s rounds, 5 rounds from seed 8,000,000. Only driving straight and smooth between far fuels keeps the tank going; a wasteful driver runs dry, and the round's points stop there.
- Scored like every round skill: game points (driving and fuel) as a share of the heuristic's. 8 skills in 4 groups; the suite stays version 1 (agents start from scratch).
- The map is a test map: never in a training mix, and training on it warns.

## Consequences

- Candidates measured, 8 rounds each (points, rounds dry): 600 px apart in 45 s rounds, navigator 1,972 and 0, heuristic 2,124 and 0; **750 px, 45 s: navigator 1,920 and 0, heuristic 1,944 and 1**; 750 px, 60 s: 2,538 and 0, 2,439 and 1; 900 px, 60 s: 2,486 and 0, 2,331 and 1. A random driver ran dry in every round of every one, at about 25 s. At 750 px and 45 s the heuristic sits at the edge (1 of 8 dry), so a driver a little more wasteful runs dry; longer rounds separated no better and would make scoring each checkpoint slower.
- The suite plays about 30 % more game time per checkpoint (225 s of 990).
