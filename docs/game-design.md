# Game design

## Long-term vision

A 2D car game where RL agents (and you) drive:

- Walls. Hitting one costs health by impact speed, and a wrecked car (health 0) is out.
- Fuel spawns on the map, up to 3 at once (step 9: fuel replaces the fuels the game started with). The tank is limited and every throttle and turn burns it, so an agent must plan which fuel to take next.
- Multiplayer: several cars, controlled by agents or humans.
- Later: weapons and skills. Deliberately postponed to keep the basics correct first.

## First goal (roadmap step 3)

One car alone in the box map (the field border, no inner walls, no fuel). **A skilled agent survives the whole round while driving and collecting fuels.**

### Round and game

| Rule | Value |
|---|---|
| Round start | When you drive, the round (and its timer) starts with your first driving key, so you can get ready. Agents and baselines start at once |
| Round length | 60 seconds = **7,200 steps** at 120 steps/s ([decision 008](decisions/008-fixed-timestep-clock.md)). The timer counts simulation steps, never real time, to keep replays deterministic |
| Rounds per game | 1 (configurable, other rules between rounds decided when it goes above 1). Round length, rounds, and scoring live in rules files (`rules/standard.json`) since roadmap step 4g ([decision 013](decisions/013-game-rules-files.md)) |
| Game score | **Accumulates across all rounds of a game**, and resets only when a new game starts. With several rounds, an agent's episode will likely be a whole game, so it learns to play for the total |
| Round ends | When the timer hits 0, or when the car is wrecked |
| Wall hits | Touching the border or a wall inside the field (driving or turning into it) costs health by impact speed, and the car slides along the wall, or stops if it hit head-on (see Car health). At 0 health the car is **wrecked**: out of the round. Later, with several cars, the round continues until the timer ends or every car is out. The HUD shows WRECKED, the event log records it, and R restarts |

The HUD shows the remaining time.

### Rewards

**Implemented in step 3g.** The env returns each step's points as the reward, and the HUD shows score, distance points, fuel points, and the last step.

These are the **game score** rules: the same for everyone, shown in the HUD and leaderboards. A time-attack variant (faster fuels score more) is a later idea, as its own rules file. What an agent learns from is its **reward profile** (roadmap step 4c, [decision 011](decisions/011-reward-profiles.md)), which can weight things differently without changing the game score.

**The default reward profile** (`rewards/default.json`, since 7e, [decision 041](decisions/041-progress-reward.md)) doesn't use game points at all: **progress** toward the fuel along a drivable path around the walls (+1 per px closer when driving forward, nothing while reversing, -1 per px farther in any gear, so following the route pays about as much as the fuel it leads to, 7f11, [decision 067](decisions/067-progress-pays-more.md); so circling, rocking, or backing to fuels can't pay), **+500 per fuel** (the best there is), -100 per wall contact (again only after 0.5 s clear of walls, so wiggling against one counts once, [decision 057](decisions/057-contact-after-a-gap.md)), -1000 per full loss of health, -3000 for a wreck, -0.25 per step stopped, and being stuck (no closer along the route than its best) costs nothing for 3 s, then rises to -0.5 per step at 10 s (7f14, [decision 071](decisions/071-stuck-cost.md)). The path is only for grading the agent's actions: the agent never sees it.

| Event | Reward |
|---|---|
| Driving | Nothing since 9a2 (`distance_step` 0): points would pay for driving around instead of racing for fuel. A rules file can still give +1 per N px forward |
| Fuel collected | **+100** |
| Wall hit | No game points lost, but a wreck ends the round, so all future points are lost. (The agent's default reward profile gives -100 per wall contact, even a harmless bump, -1000 per full loss of health, -3000 for a wreck, and -0.25 per step stopped; the game score doesn't) |

### Car health

**Implemented in step 5a4** ([decision 016](decisions/016-car-health-and-wall-hits.md)). The numbers live in the rules file:

```json
"collisions": {"health": 100, "safe_speed": 60, "lethal_speed": 240, "scrape_damage": 0.1}
```

| Word | Means |
|---|---|
| **Bump** | A hit at or below `safe_speed` (px/s): no damage |
| **Hit** | Damage = `health × (impact − safe_speed) / (lethal_speed − safe_speed)`, at most all of it |
| **Scrape** | Sliding along a wall costs `scrape_damage` health per px slid (1 per 10 px), and can wreck the car. A head-on push slides nothing, so it costs nothing |
| **Wrecked** | Health reaches 0: out of the round |

- **Impact speed** is the car's speed *into* the wall, so grazing a wall hurts less than hitting it head-on. A turn that pushes a corner into the wall is a hit too, at that corner's speed; the turn doesn't happen.
- **After a hit** the car **slides along the wall**: it loses the part of its motion into the wall and keeps the part along it (speed × that share), so it can steer away. A head-on hit stops it exactly where it touched. Pushing on into the wall is the same contact: no more impact damage, only scrape damage for the distance slid, and a head-on push stays stopped.
- A turn into the wall is blocked, but keeps the speed.
- Rules can make any contact wreck, like the game before 5a4: `safe_speed` = `lethal_speed` = 0 and `scrape_damage` = 0. (That was `rules/classic.json`, removed on 2026-09-28; the tests keep checking it with a scratch rules file.)
- **In the window:** a thin bar above the car (7c4: green above 60 %, amber from 30 %, red below; level on screen, so it never turns with the car or covers it; fuel joins as a second bar under it in step 9). A hit car blinks red for 0.5 s (it stays red while scraping), a wrecked car turns dark red, and the event line shows the hit (`Hit the wall at 180 px/s: -67 health`) and each scrape once it ends (`Scraped the wall for 120 px: -12 health`). Blink timings are display settings (`hud.hit_flash_seconds`, `hud.hit_blink_seconds`).

### Fuel

The game's targets were called checkpoints until step 9a1 ([decision 075](decisions/075-checkpoints-are-fuel.md)); they're fuel now. Since 9a2 they work as fuel ([decision 076](decisions/076-fuel-rules.md)): a car's tank (100, full at the start) burns 1/s idle, +4/s with gas or reverse, +1/s while turning, nothing for braking; each fuel puts back 40, up to the full tank. Empty, the engine dies: the car coasts, and once it stops it's out of the round (coasting into a fuel restarts it). A fuel bar sits under the health bar above the car.

**Implemented in step 3g**, as generic triggers (see Hazards below): a `Trigger` circle plus `ScoreReward` and `Respawn` effects. The demo picks a fresh seed each round, shown in the bottom bar; agents and tests use `game.seed`.

**Since step 4b**, the rules live in the stage file, and spawns follow a **spawn schedule**: stage + seed decide the whole sequence, so every driver gets the same fuels ([decision 009](decisions/009-stage-format-and-spawn-schedules.md)).

- Up to 3 on the field at once (a stage's `at_once`, 1 to 3; the `skill_` test maps keep 1). Collecting one spawns the next.
- Random position from a **seeded** random number generator, so replays reproduce it.
- Radius 15 px. Spawns at least 100 px from any car and from the other fuels, and 40 px from the border and any wall.
- Or **scripted**: the stage lists the points, played in order and looping; with 3 at once they're a sliding window (the next 3 not taken). With `"start": "seeded"` (7d5a), the first one is picked from the seed, so a training course practices every zone ([decision 050](decisions/050-map-mixes.md)).

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
- The game is on the left and the car and its AI on the right (7f10, [decision 066](decisions/066-game-left-ai-right.md)): the speed and steering as instruments, one SENSES radar with the fuel compass and the route waypoint on its rim, and when an agent drives, MIND (its odds for each action, as a grid). With the lines (H), the field also shows the agent's remembered route waypoint, the OBJECTIVE card how long it's been stuck, and when an agent drives, a MIND card shows its next move's odds and its outlook (7f8, [decision 062](decisions/062-seeing-what-the-agent-senses.md)).
- **O** opens your display settings in any game window (7c5, [decision 040](decisions/040-settings-of-yours.md)): the car's bars above or below it, which lines show, the faint full route (7f8), the trail, the camera on big stages, the map intro, and the FPS cap.

Watching a driver, holding a driving key takes over until you let go (7f9, [decision 064](decisions/064-taking-over-while-watching.md)); watching an agent, C saves those takeovers as corrections it can learn from (7g, [decision 068](decisions/068-expert-labelling.md)). The agent's action is 5 bools: `(turn_left, turn_right, gas, reverse, brake)`. **Stopped, an agent must press gas or reverse** (7f6, [decision 060](decisions/060-a-stopped-agent-moves.md)): at speed 0 the other pedals can't move the car and steering needs speed, so those choices are blocked; moving, every action is open. Keyboard driving is unchanged.

### Sensors

Rays only detect things a car can hit (the border and walls now; later other cars and explosion hazards). They pass through fuels and fuel, which agents perceive through the compass inputs instead (see Observation).

12 rays around the car's heading, denser in front (7f3, [decision 059](decisions/059-twelve-rays-and-instruments.md)): 0°, ±15°, ±30°, ±45°, ±90°, ±135°, and 180°: front, front-left 15°, front-left 30°, front-left (45°), left, back-left, back, back-right, right, front-right (45°), front-right 30°, front-right 15°. A 48 px gap shows from 184 px away and a 30 px pillar from 115 px (with 8 rays 45° apart: 63 and 39 px). Each ray starts where it leaves the car's body, so distance 0 means touching. Distances are exact floats. **Implemented in step 3e.**

### Observation (what the agent sees)

**Implemented in step 3h** (`src/sim/observation.py`, layout version 1; health added in 5a4; 12 rays in 7f3; the route and stuck timer in 7f7). 23 float32 numbers:

| # | Input | Range and normalization |
|---|---|---|
| 0-11 | Ray distances, in the rays' order around the car (front, front-left 15°, 30°, 45°, left, back-left, back, back-right, right, front-right 45°, 30°, 15°) | 0 to 1, divided by 980.5 px (the box's diagonal) on every map (7d2) |
| 12 | Speed | -⅓ (full reverse) to 1, divided by max speed |
| 13 | Steering wheel position | -1 (full right) to 1 (full left) |
| 14 | Fuel distance | 0 to 1, divided by 980.5 px on every map (7d2) |
| 15 | Fuel sin (relative angle) | -1 to 1, positive = to the left |
| 16 | Fuel cos (relative angle) | -1 to 1, positive = ahead |
| 17 | Route distance (remembered, 7f7) | 0 to 1, divided by 980.5 px: the drivable route's length, refreshed with the waypoint |
| 18 | Route sin (the waypoint's relative angle) | -1 to 1, positive = to the left: a remembered point about one corner ahead along the route (the fuel itself when in sight), refreshed when reached (45 px), passed, or every 2 s |
| 19 | Route cos | -1 to 1, positive = ahead |
| 20 | Stuck | 0 to 1: seconds since the car last got closer along the route, over 10 s |
| 21 | Time left in the round | 1 at the start, down to 0 |
| 22 | Health | 1 (full) down to 0 (wrecked) |

- **Direction is relative to the car**, like a compass ("ahead-left, fairly close"). Sin and cos avoid the jump from 359° to 0°.
- **Fixed size:** a neural network needs a fixed number of inputs. Objects that vary in count use the **nearest K of each type**, with empty slots filled by zeros plus an "absent" flag. For now there's always exactly 1 fuel (up to 3 in step 9a2).
- **Fuel phase (9b):** adds the fuel level, plus the 3 fuels nearest by route, each with the straight compass and the route sensor.

All values above are starting points, kept in config so experiments can change them.

## Later phases

- Inner walls in stage files (done in step 7a: rectangles, [decision 033](decisions/033-walls-in-the-simulation.md); the `pillars` and `s_curve` stages), a camera for stages bigger than the view (step 7b: follow with a map card, or fit, F; a map intro each round, and edge markers for a fuel out of view), and a map editor (step 7c1: `make edit_map`)
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

Hazards, fuel, and later skills are all the same pattern: **when a car touches X, apply effect Y**.

| Piece | Kind | Example |
|---|---|---|
| Hazard or fuel on the map | Entity with a `Trigger` component (shape) plus an effect | Oil slick zone with effect "slow down 50%" |
| Effect on a car | Component on the car, with a duration **in steps** | `Slowed(factor=0.5, steps_left=240)`, `Stunned(steps_left=360)` |
| Detection | One trigger system: car overlaps zone, then apply the effect | Same system for every trigger type |
| Durations | A status system counts down and removes expired effects | "2 seconds" = 240 steps, so it stays deterministic |
| Explosion | The same "car eliminated" path as a wreck | No separate game-over logic |

Movement and steering read the effect components: `Slowed` scales the speed, and `Stunned` ignores the car's input.

### Groundwork during step 3

**Done** in steps 3f and 3g. Cheap, because step 3 needed these anyway:

1. **Build fuels (now fuel) as a generic trigger + effect**, not a special case. Hazards then become new effect types, not new systems.
2. **Handle wrecks as a generic "eliminate car" event**, so explosions and later weapons reuse it.
3. **Keep every duration in steps**, never seconds of real time.

Not built early: `Slowed`, `Stunned`, and other effects. Each one is a new component plus a few lines in movement or steering, added when needed.

### Agent observation

Agents must see hazards to avoid them: nearest K hazards in the observation, or rays that detect them. The observation layout grows with each phase, so **every trained agent records the observation layout version it was trained on**. That way incompatible agents are caught at load time.
