# 021: The window layout on four sides

**Date:** 2026-09-27. **Status:** Implemented (`src/render/layout.py`, `src/render/panels.py`), between roadmap steps 5c and 6.

## Context

The window had a two-row top bar, one right panel, and a one-line bottom bar. With health, modes (REC, REPLAY, SHOWCASE), and more agent information, it got cluttered: the mode label collided with the HEALTH gauge, and the right panel was full.

## Decision

Group information by what you look at, and how often it changes, in **modular boxes** (cards):

| Where | Boxes |
|---|---|
| Top, one row above the field | Gauges on the left (HEALTH; fuel in step 9), then round, time, big score, and car status on the right (the status has a fixed slot, so a change never moves the rest) |
| Left: the game | DRIVER (name, and the mode: REC, REPLAY 2×, SHOWCASE 4/8) · GAME (stage, rules, spawns, seed) · SCORE (distance, checkpoints) · LEADERBOARD, right below the score · AGENT (reward profile, reward this game, simulation step, sim rate) |
| Right: the car | CAR (speed, stopping distance, pedal, steering, heading, position, inputs) · SENSORS · OBJECTIVE · DISPLAY (FPS, vsync, and "? shortcuts") |

- Every section is its own box, with the same 16 px gap between all boxes. The side panels are stacks of boxes (no outer border).
- **No bottom bar:** the event line and the "last step" rows (almost always 0, and hard to read at 120 steps/s) were removed. Step and sim rate moved to AGENT, FPS to DISPLAY.
- **Shortcuts on demand:** `?` opens a box over the field with every key of the current mode (live play, recording, replay, showcase), and closes it again. Modes list their keys as (key, action) pairs.
- **Window controls** (every mode): Esc closes an open box first. Otherwise it asks "Quit?" (Enter quits, Esc goes back), except when the round is over: then it quits at once, and the round-over box says "R restarts · Esc quits". Closing the window always quits. P pauses and resumes (SPACE too in replays and the showcase). While a box is open, the game is frozen.
- **Your round waits for your first driving key:** the timer doesn't run while you get ready, and recordings don't start with idle waiting (which had taught clones to stay stopped, [decision 019](019-imitation-agents.md)). Agents and baselines start at once.
- Sized for the laptop screen (1,470 px wide): left panel 250 px, right 260 px, window 1,429 × 572 for the box stage.
- Every row shortens its label and value with "…" to fit, and the value keeps at least half the row (a long leaderboard name never hides the score).
- The field border is drawn in the panels' gray (it was white), so the window reads as one set of boxes.
- **Font: Helvetica Neue** (`theme.FONT_FAMILY`; it was Courier). Crisp at small sizes, compact, and its digits all have the same width, so changing numbers don't wobble. The shortcuts box draws real columns (keys right-aligned, actions left-aligned) instead of lining them up with spaces. SF (the macOS system font) rendered with uneven digit spacing in pygame, and Avenir Next's regular weight came out almost bold.

## Consequences

- Both side panels have room left for later sections (fuel, more cars).
- A stage much bigger than the box would make the window too wide: that's step 7's camera.
- **Reward bar** (every game window, added later: [decision 032](032-reward-by-term.md)): the agent reward by term, gains and costs, under the field (under the playback bar when there is one). The window grows 60 px for it.
- **Playback bar** (replays and the showcase): a video-player-style bar in its own box under the field (the window grows 60 px taller for it; live play keeps its size): play or pause icon, time, progress, and the speeds 0.5× 1× 2× 4× with the current one lit. A speed change, pause, or resume also flashes big in the middle of the field for 0.7 s. The DRIVER card's mode label no longer repeats the speed.
- **Replay trail (T),** in replays and the showcase (each checkpoint starts a new trail): where the car has driven since the round began, under the car. The last 2 s are bright and thicker, then it fades from the car's blue to a muted gray over 20 s, never invisible. Independent of the sensor lines (H). Display only: a point every 2 steps, recorded as the replay plays, cleared on restart. A full 60 s trail (3,601 points) costs 0.8 ms per frame (measured).
