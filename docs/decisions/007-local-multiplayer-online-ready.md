# 007: Local multiplayer now, designed to go online later

**Date:** 2026-09-25. **Status:** Accepted, not implemented (roadmap step 8).

## Context

Games should mix agents and human players. For now, humans play on devices connected to the same computer: keyboards and gamepads, including Bluetooth controllers. Online play (players on other computers) is wanted later, and it's much bigger: a server that runs the game, clients that send inputs, and handling network lag.

## Decision

Build local multiplayer only. Keep four rules so online can be added later without redesigning:

1. **Devices never touch the simulation.** Every controller (keyboard, gamepad, agent, replay, later a network client) only produces an `ActionInput` for its car. The simulation consumes one input per car per step.
2. **Inputs are indexed by step:** "car 2 pressed gas at step 1,834". Online play can then exchange these small input messages instead of game state (lockstep networking), and replays use the same format.
3. **The simulation stays deterministic** (already a rule, see [conventions](../conventions.md#determinism-must-keep)). The same setup plus the same inputs gives the same game on every machine.
4. **A game setup is plain data:** map, rounds, seed, and slots (each slot says which controller type drives which car). It can be saved as a preset, and later sent over a network. Cars belong to slots, not to devices.

## Consequences

- Replays, local play, and future online play share one input stream format.
- The lobby assigns devices to slots, and nothing else in the code knows about devices.
- Online multiplayer is listed under "Later" in the [roadmap](../roadmap.md).
