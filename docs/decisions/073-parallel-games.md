# 073: Several games at once, as many as the machine has room for

**Date:** 2026-10-04. **Status:** Accepted. Built in roadmap 8a (`src/experiments/games.py`, `game_worker.py`, `game_count.py`, `training.py`, `src/agents/ppo.py`, `src/control/guard.py`); the Training tab and the Runs tab follow in 8b.

## Context

Every new feature changes the observation, so every agent trains again, often more than once while the feature is tuned. Training played one game: the network waited on the game, and the game on the network. You also work on this laptop while it trains, so more games must never crowd you out (decision 038).

## Decision

- **One network, several games.** Each game runs in its own worker process, started as a plain subprocess (`python -m src.experiments.game_worker`), so it never imports `app.py` or torch: about 0.05 GB each. The games step together: one network pass decides for all of them, each game holds its decision for `action_repeat` steps, and answers with what happened. One game plays in the training process itself, with no worker.
- **The rollout stays 2,048 decisions in total**, split over the games (512 each with 4). Updates come as often as with one game, so runs compare at the same decision count, and every update sees every game's map at once. Each game's advantages come from its own decisions in order (its own value at the end of its piece), then the update learns from all of them together. One game gives exactly the run it gave before step 8 (checked against the last commit on a stage and a mix).
- **Rounds:** the i-th round to start uses seed `first_seed + i`; `metrics.csv` rows come in the order rounds end, with a `game` column. A mix's rounds each take the map furthest behind (one game: in turn, as before), and a curriculum counts a round when it starts, so games starting together get different maps. The level is shared.
- **Replays:** a worker keeps its finished round until the training says whether it's a new best on its map; only those are saved.
- **How many games** (`GameCount`, after every update): as many as fit at the start, up to the run's most (`--games`, default 4). One fewer, after its round, when memory reaches amber (88 %) or the whole machine's CPU stays above 85 % for 10 s. One more after 60 s with memory below 80 % and CPU below 60 %, if it fits. Never more than the cores minus the 2 kept free, minus the training process, minus other heavy jobs; never fewer than 1. Each change is printed, and `learning.csv` has a `games` column.
- **Resume starts fresh rounds.** The rounds playing at the stop are dropped, and resuming the same state twice gives the same run. A fixed number of games always gives the same run from the same seed; with the count following the machine, a run can't be re-created from its seed, but every round still replays exactly.
- **Nothing left behind:** a worker ignores Ctrl+C and ends when its pipe closes, so a training that ends, stops, or is killed takes its workers with it. The guard counts the workers' memory as the job's, and a training's estimate adds 0.1 GB per worker.

## Consequences

- **Measured (8a, `skill_training`, `finetune`, the medium model, 30,720 decisions):** 1 game 821 decisions a second, 2 games 1,023, 4 games 984. The games alone scale (4 workers on the arena: 5,814 a second, 2.4 times one), but the games step together, so the slowest sets the pace: `course_small` takes 3.7 ms a decision, the others 0.15 to 1.0 ms. Its route sense recomputes the waypoint almost every decision there (a new waypoint inside the 45 px reach counts as reached at once). That's a separate fix: it changes what agents sense.
- This Mac has 4 performance and 6 efficiency cores, not 10 equal ones; low priority made no difference to the speed measured.
- Decision 015's exact resume by re-simulating the current episode is replaced by fresh rounds.
