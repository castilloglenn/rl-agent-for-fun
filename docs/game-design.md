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
| Round length | 60 seconds = **5,400 steps** at 90 FPS. The timer counts simulation steps, never real time, to keep replays deterministic |
| Rounds per game | 1 (configurable, rules between rounds decided when it goes above 1) |
| Round ends | When the timer hits 0, or when the car crashes |
| Crash | Touching the border = game over for that car. Later, with several cars, the round continues until the timer ends or every car is out |

The HUD shows the remaining time.

### Rewards

| Event | Reward |
|---|---|
| Driving forward | **+1 per 10 px** driven. The distance accumulates across frames, so slow driving still earns |
| Stopped or reversing | 0 (so reversing back and forth can't farm points) |
| Checkpoint collected | **+100** |
| Crash | Ends the round, so all future reward is lost |

### Checkpoints

- One on the field at a time. Collecting it spawns the next one.
- Random position from a **seeded** random number generator, so replays reproduce it.
- Radius 15 px. Spawns at least 100 px from the car and 40 px from the border.

### Controls (realistic driving)

| Input | Effect |
|---|---|
| W / Up (gas) | Accelerate |
| Release gas | The car keeps rolling, with mild drag: full speed rolls to a stop in about 3 seconds |
| SPACE (brake) | Strong deceleration on every frame it's held. Tapping slows the car, holding stops it |
| S / Down (reverse) | While moving forward it brakes first, then reverses once stopped |
| A/D, Left/Right (steer) | Turn rate follows speed, so a stopped car can't turn |

The agent's action becomes 5 bools: `(turn_left, turn_right, gas, reverse, brake)`.

### Sensors

8 rays at 0°, 45°, 90°, and so on around the car's heading, replacing today's 4 (front, ±30°, back). Each ray starts where it leaves the car's body, so distance 0 means touching.

### Observation (what the agent sees)

About 13 numbers, all normalized to a 0 to 1 or -1 to 1 range:

| Input | Count |
|---|---|
| 8 ray distances (to walls) | 8 |
| Speed | 1 |
| Checkpoint: distance, plus sin and cos of its angle relative to the car's heading | 3 |
| Time left in the round (fraction) | 1 |

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
| Effect on a car | Component on the car, with a duration **in steps** | `Slowed(factor=0.5, steps_left=180)`, `Stunned(steps_left=270)` |
| Detection | One trigger system: car overlaps zone, then apply the effect | Same system for every trigger type |
| Durations | A status system counts down and removes expired effects | "2 seconds" = 180 steps, so it stays deterministic |
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
