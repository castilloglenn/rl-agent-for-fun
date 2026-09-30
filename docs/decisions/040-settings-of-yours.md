# 040: Settings of yours, display only

**Date:** 2026-09-30. **Status:** Accepted. Built in roadmap 7c5 (`src/utils/settings.py`, the renderer's SETTINGS box); the control center's Settings tab follows in 7c6.

## Context

Display choices were code defaults in `src/config.py`, changed only by command-line flags (`--maze_car.show_bounds=false`) or keys that reset every window (H, T, F). The health bar moved above the car (7c4), and you wanted to choose above or below, plus a place for more such choices, reachable from the game window and the control center.

## Decision

- **One file of yours:** `user/settings.json`, out of git (decision 039). **Display only:** the car's bars (above or below, always or only when damaged), the lines (rays, hitbox, and the checkpoint guide together), the trail when watching or replaying, big stages starting in follow or fit, the map intro, and the FPS cap. Nothing in it changes the simulation, so replays, runs, and scores never depend on it.
- **In every game window, O** opens a SETTINGS box: Up and Down pick, Left and Right change, each change applies at once and is saved, Esc or O closes. The game waits while it's open (like the shortcuts box). ? lists O in every mode, and the DISPLAY card hints it.
- **Keys and settings are one thing:** H is the lines setting, T the trail setting, and F (on a big stage) the camera setting, so pressing a key changes the setting and saves it, and the box shows what the keys set. (First built with separate rays, hitbox, and guide switches that H didn't touch: they drifted apart, so they became one.)
- **Safe to hand-edit:** a missing or unreadable file, an unknown key, or a value that isn't one of the choices falls back to the default (a value must match a choice's type too: `1` isn't `on`).
- **Where it flows:** `app.py` points `window.settings_file` at `user/settings.json`, a presentation key (never saved in replays or runs). An empty value, the default, keeps the defaults in memory, so tests never read or write your file.
- **How settings meet config:** a setting narrows its config key: rays show only if the lines setting is on and `show_collision_distance` allows them (the hitbox: `show_bounds`), the map intro only if `window.map_intro` does, and the FPS cap uses the setting, else `display.max_fps`.

## Consequences

- The control center's Settings tab (7c6) edits the same file, so both places always agree.
- Future display choices (fuel's bar in step 9, more cars' bars in step 8) join the same list.
