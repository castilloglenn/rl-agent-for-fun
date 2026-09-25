# Game design

## Long-term vision

A 2D car game where RL agents (and you) drive:

- Walls. A crash is game over for that car.
- Fuel and checkpoints spawn on the map. Fuel capacity is limited, so an agent must weigh chasing fuel against chasing checkpoints or other high-reward spots.
- Multiplayer: several cars, controlled by agents or humans.
- Later: weapons and skills. Deliberately postponed to keep the basics correct first.

## First goal (roadmap step 3)

One car alone in the box map (the field border, no inner walls, no fuel). **A skilled agent survives the whole round while driving and collecting checkpoints.**

### Round and game

| Rule | Value |
|---|---|
| Round length | 60 seconds = **7,200 steps** at 120 steps/s ([decision 008](decisions/008-fixed-timestep-clock.md)). The timer counts simulation steps, never real time, to keep replays deterministic |
| Rounds per game | 1 (configurable, other rules between rounds decided when it goes above 1) |
| Game score | **Accumulates across all rounds of a game**, and resets only when a new game starts. With several rounds, an agent's episode will likely be a whole game, so it learns to play for the total |
| Round ends | When the timer hits 0, or when the car crashes |
| Crash | Touching the border (driving or turning into it) = game over for that car. Later, with several cars, the round continues until the timer ends or every car is out. **Implemented in step 3f**: the HUD shows CRASHED, the event log records it, and R restarts |

The HUD shows the remaining time.

### Rewards

**Implemented in step 3g.** The env returns each step's points as the reward, and the HUD shows score, distance points, checkpoint points, and the last step.

| Event | Reward |
|---|---|
| Driving forward | **+1 per 10 px** driven. The distance accumulates across frames, so slow driving still earns |
| Stopped or reversing | 0 (so reversing back and forth can't farm points) |
| Checkpoint collected | **+100** |
| Crash | Ends the round, so all future reward is lost |

### Checkpoints

**Implemented in step 3g**, as generic triggers (see Hazards below): a `Trigger` circle plus `ScoreReward` and `Respawn` effects. The demo picks a fresh seed each round, shown in the bottom bar; agents and tests use `game.seed`.

**Since step 4b**, the rules live in the stage file, and spawns follow a **spawn schedule**: stage + seed decide the whole sequence, so every driver gets the same checkpoints ([decision 009](decisions/009-stage-format-and-spawn-schedules.md)).

- One on the field at a time. Collecting it spawns the next one.
- Random position from a **seeded** random number generator, so replays reproduce it.
- Radius 15 px. Spawns at least 100 px from the car and 40 px from the border.

### Controls (realistic driving)

| Input | Effect |
|---|---|
| W / Up (gas) | Accelerate at 200 px/s², up to 300 px/s (0 to max in 1.5 s). While rolling backward, it brakes first |
| Release all pedals | The car keeps rolling, with mild drag (100 px/s²): max speed rolls to a stop in 3 s |
| SPACE (brake) | Strong deceleration (600 px/s²) on every frame it's held: max speed to a stop in 0.5 s. Tapping slows the car, holding stops it |
| S / Down (reverse) | While moving forward it brakes first, then reverses once stopped: 100 px/s², up to 100 px/s |
| A/D, Left/Right (steer) | Turns a **steering wheel**: 0.25 s from center to full lock, and it self-centers in 0.15 s when released. Switching sides passes through center. Turn rate = wheel position × up to 240°/s, scaled by speed up to 120 px/s, so a stopped car can't turn (the wheel still moves). Steering flips while rolling backward. Left and right together re-center |

- Pedal priority: brake beats gas, and gas beats reverse.
- **Calibrated for human play:** at max speed, the car crosses the field in about 2.9 s. One reaction time (about 0.25 s) covers 75 px (3 car lengths), and so does the braking distance, so an obstacle 150 px ahead is always avoidable. Turning radius: 72 px at max speed, 29 px at 120 px/s.
- All values are in config (`car.*`, see [config](config.md)). **Implemented in step 3b.**
- The HUD shows the current pedal state (Idle, Gas, Coasting, Braking, Reverse) and the wheel position (for example "Left 60 %").

The agent's action is 5 bools: `(turn_left, turn_right, gas, reverse, brake)`.

### Sensors

Rays only detect things that can crash a car (the border now; later walls, other cars, and explosion hazards). They pass through checkpoints and fuel, which agents perceive through the compass inputs instead (see Observation).

8 rays at 0°, ±45°, ±90°, ±135°, and 180° around the car's heading: front, front-left, left, back-left, back, back-right, right, front-right. Each ray starts where it leaves the car's body, so distance 0 means touching. Distances are exact floats. **Implemented in step 3e.**

### Observation (what the agent sees)

**Implemented in step 3h** (`src/sim/observation.py`, layout version 1). 14 float32 numbers:

| # | Input | Range and normalization |
|---|---|---|
| 0-7 | Ray distances (front, front-left, left, back-left, back, back-right, right, front-right) | 0 to 1, divided by the field diagonal (978 px) |
| 8 | Speed | -⅓ (full reverse) to 1, divided by max speed |
| 9 | Steering wheel position | -1 (full right) to 1 (full left) |
| 10 | Checkpoint distance | 0 to 1, divided by the field diagonal |
| 11 | Checkpoint sin (relative angle) | -1 to 1, positive = to the left |
| 12 | Checkpoint cos (relative angle) | -1 to 1, positive = ahead |
| 13 | Time left in the round | 1 at the start, down to 0 |

- **Direction is relative to the car**, like a compass ("ahead-left, fairly close"). Sin and cos avoid the jump from 359° to 0°.
- **Fixed size:** a neural network needs a fixed number of inputs. Objects that vary in count use the **nearest K of each type**, with empty slots filled by zeros plus an "absent" flag. For now there's always exactly 1 checkpoint.
- **Fuel phase:** adds the fuel level, plus the nearest K fuels (for example K = 3) in the same distance + sin/cos format.

All values above are starting points, kept in config so experiments can change them.

## Later phases

- Map files and inner walls (rectangles first: [decision 006](decisions/006-rectangle-walls-first.md))
- Fuel system
- Multiple rounds per game
- Multiple cars and car-vs-car collision
- Hazards (below)
- Weapons and skills

## Hazards (future)

Objects in the environment that hurt cars:

| Hazard | Effect |
|---|---|
| Slowdown | Car speed reduced for X seconds |
| Tire break | Car stunned (ignores input) for X seconds |
| Explosion | Game over for that car |

### How it fits the ECS

Hazards, checkpoints, fuel, and later skills are all the same pattern: **when a car touches X, apply effect Y**.

| Piece | Kind | Example |
|---|---|---|
| Hazard, checkpoint, or fuel on the map | Entity with a `Trigger` component (shape) plus an effect | Oil slick zone with effect "slow down 50%" |
| Effect on a car | Component on the car, with a duration **in steps** | `Slowed(factor=0.5, steps_left=240)`, `Stunned(steps_left=360)` |
| Detection | One trigger system: car overlaps zone, then apply the effect | Same system for every trigger type |
| Durations | A status system counts down and removes expired effects | "2 seconds" = 240 steps, so it stays deterministic |
| Explosion | The same "car eliminated" path as a wall crash | No separate game-over logic |

Movement and steering read the effect components: `Slowed` scales the speed, and `Stunned` ignores the car's input.

### Groundwork during step 3

Cheap, because step 3 needs these anyway:

1. **Build checkpoints as a generic trigger + effect**, not a special case. Hazards and fuel then become new effect types, not new systems.
2. **Handle crashes as a generic "eliminate car" event**, so explosions and later weapons reuse it.
3. **Keep every duration in steps**, never seconds of real time.

Not built early: `Slowed`, `Stunned`, and other effects. Each one is a new component plus a few lines in movement or steering, added when needed.

### Agent observation

Agents must see hazards to avoid them: nearest K hazards in the observation, or rays that detect them. The observation layout grows with each phase, so **every trained agent records the observation layout version it was trained on**. That way incompatible agents are caught at load time.
