# 022: The control center, in pygame, over files and processes

**Date:** 2026-09-27. **Status:** Accepted. Step 6a implemented (`src/control/`, `make control`). 6b to 6d planned.

## Context

Step 6 is a control center: every command, training setup, runs, agents, and file editing in one window. The roadmap assumed a messaging layer (IPC) between the control center, training, and game windows, and left the UI library open (`pygame_gui`, NOT VERIFIED with pygame-ce).

## Decision

- **All pygame** (your choice, over a local web page or Qt), with **`pygame_gui` 0.6.14** for widgets: buttons, text fields, dropdowns, and scrolling lists. It requires pygame-ce 2.5.3 or newer (verified). Charts and cards are hand-drawn, like the game HUD.
- **The same look** as the game window: dark flat boxes, gray borders, the accent color, and Helvetica Neue. pygame_gui only uses a font set on each element type, so the theme sets it per element. The console and job list use Menlo (monospace), so command output lines up.
- **Its own consolidated actions, grouped by the natural steps** (Play, Replays, Experiments, Agents, Develop). A terminal command takes at most one parameter, so the Makefile has one target per variant (42). In a window an action has fields instead, so 19 actions cover them all: for example one **Run episodes** (driver, name, episodes, seed, stage, rules, round seconds, reward) replaces `run_heuristic`, `run_random`, `run_driver`, `run_episodes`, `run_reward`, `run_rules`, `run_stage`, `run_seconds`, and `run_agent`. A test maps every make target to the action that covers it, so nothing is lost. (The first 6a version listed the make targets themselves; too many near-duplicates.)
- **The Makefile stays for the terminal**, unchanged, and every action shows the exact `python app.py …` command it runs. (A typed command line under the console was dropped: the actions cover everything.)
- **A big console** (about 35 % of the window), and **the fields scroll** with the mouse wheel when an action has more than fit, with a thin indicator. The title and description stay put. The scrolling is done by hand, because pygame_gui's scrolling container would clip an open dropdown's list at its edge.
- **No messaging layer: files and processes.** All state is already in files (runs, agents, recordings), so the control center reads files to show state and starts processes to act. Every command runs as its own process (`python app.py ...`, like make), so a closed or crashed game window never takes down the control center or a training run.
- **Job controls are signals:** Stop is Ctrl+C (SIGINT, so training keeps its exact resume state; a second Stop ends it), Pause freezes the process in place (SIGSTOP), and Resume continues it (SIGCONT). That's also the roadmap's "pause training in place".
- **Fields are dropdowns from the files on disk** (agents, checkpoints, drivers, rules, rewards, stages, models, trainers, datasets, suites, runs, recordings, test files), so a typo can't happen. New names (a new agent, a player) and numbers are typed, and a blank optional field shows what blank means ("blank: the rules' own").
- **Tabs across the top** (retro: the open tab is a lit box, later ones are dimmed with their step), instead of a sidebar, so the boxes below get the full width.
- **Quitting asks first**, in the game window's style: a QUIT? box that dims the window, says how many running jobs would be stopped, and has **Cancel (Esc)** and **Confirm (Enter)**. Nothing behind it reacts while it's open, and closing the window again confirms. (pygame_gui's own confirmation dialog was cramped and didn't match.)

## Consequences

- 6a gives every command in a window, with live output. The tabs for training (6b), runs (6b), agents (6c), and files (6d) show dimmed until built.
- Two new dependencies: `pygame_gui` and `python-i18n`.
- Commands that open a game window (play, replay, showcase) still open their own window, as a separate process. That window **prints its events** as they happen (hits, scrapes, checkpoints, wrecks, round over, clicks), so the job's console is the round's live feed. Stop (Ctrl+C) ends a game window cleanly, and a drive in progress still saves its recording.
- **Open dropdowns stand out:** their list is nearly black with an accent border, darker than the fields behind it. The dimmed hints of blank fields hide while a list is open (they were drawn over it).
- **The machine's vital signs**, in a strip above the tabs, refreshed every second (`psutil`, a third new dependency): CPU of the whole machine with our jobs' share (a training uses one core, so 10 % of this 10-core Mac), memory in use (total minus available, as macOS counts it) with our jobs' share, battery (and whether it's plugged in), free disk, and running jobs. Each turns amber, then red, near the edge: CPU at 70 % and 85 %, memory at 88 % and 95 % (macOS keeps about 80 % in use even when idle), battery under 40 % and 20 % while unplugged (and amber whenever unplugged), disk under 20 GB and 5 GB free.
