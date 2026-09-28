# Setup

## Environment

- Python 3.14, in `venv/` (gitignored).
- Use **pygame-ce**, not `pygame`. The reason is in [decision 001](decisions/001-pygame-ce.md). The two packages can't be installed side by side, so uninstall `pygame` first if it's present.

```
python3.14 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` is unpinned.

## Commands

One word per command, at most one parameter. `make help` lists them (it's also the default target).

| Command | Does |
|---|---|
| `make control` | The control center: the machine's vital signs (CPU, memory, battery, disk, our jobs' share), and every command below, consolidated into 28 actions with fields (dropdowns from your files), background jobs (stop, pause, resume), and a live console. The Training tab trains an agent from one form (RL, imitation, or both, for a new or existing agent), the Runs tab lists every run with its status and live learning curves, the Agents tab shows every agent (cards or a leaderboard) with its profile, and the Files tab edits reward profiles, rules, trainers, models, datasets, and suites, checked as you type, and browses your recordings (watch, keep, unkeep, delete). Rest the mouse on an item marked with a small circled "i" (and on legends, radar labels, badges, and the vital signs) for what it means |
| `make delete_run RUN=folder` | Move a run folder into the trash (`trash/`). Its checkpoints stay in its agent, and a live run is refused ([decision 027](decisions/027-trash.md)) |
| `make delete_agent AGENT=id` | Move an agent into the trash, with its training, imitation, and episode runs. Agents branched from it stay ([decision 028](decisions/028-agents-tab.md)) |
| `make keep FILE=path` | Keep a recording: move it into `kept/`, where the latest-50 limit never removes it |
| `make unkeep FILE=path` | Move a kept recording back with the recent ones (the latest-50 limit applies at your next saved round) |
| `make delete_recording FILE=path` | Move a recording into the trash ([decision 031](decisions/031-recordings-browser.md)) |
| `make trash` | What's in the trash, one entry per delete, newest first |
| `make restore TRASH=entry` | Put a trash entry's folders back where they were |
| `make empty_trash` | Delete everything in the trash for good (no question asked in the terminal; the control center asks) |
| `make vitals` | The last 30 rows of the vitals log (`logs/vitals.csv`): the machine's readings and job events while the control center was open, kept under about 200 KB, for looking into a crash ([decision 024](decisions/024-vitals-log.md)) |
| `make maze_car` | Drive with the keyboard: WASD/arrows, SPACE brakes, P pauses, R restarts, H toggles lines, ? shows all shortcuts, Esc asks before quitting (Enter quits). A round starts with your first driving key. **Every round is recorded** to `recordings/<player>/` (REC in the left panel). K keeps the last recording for good |
| `make maze_car_norecord` | Drive without recording |
| `make maze_car_heuristic` | Watch the heuristic baseline drive |
| `make maze_car_random` | Watch the random baseline drive |
| `make maze_car_driver DRIVER=name` | Any driver: `keyboard`, `random`, `heuristic`, `agent:<id>` |
| `make maze_car_player PLAYER=name` | Drive with your player name (HUD, and recordings from 4i) |
| `make maze_car_stage STAGE=name` | Another stage: a name in `stages/` (`box`, `pillars`, `s_curve`, `arena`), or a path. On a big stage (like `arena`) the view follows the car, a MAP card at the top right shows the whole stage, each round starts with a 3 s look at the whole map (a key zooms in sooner), green edge markers point to a checkpoint out of view, and F switches to an overview of the whole stage |
| `make maze_car_reward REWARD=name` | Another reward profile: a name in `rewards/`, or a path |
| `make maze_car_rules RULES=name` | Other game rules: `standard`, `sprint` (30 s), `marathon` (120 s), a name in `rules/`, or a path |
| `make maze_car_seconds SECONDS=n` | Another round length (the rules get renamed, for example `standard-90s`) |
| `make maze_car_fps FPS=n` | Cap the frame rate (0 = match the display) |
| `make recordings` | List recorded rounds per player (recent and kept counts, newest) |
| `make replay_last` | Watch your newest recording |
| `make replay FILE=path` | Watch a replay (`.jsonl` or `.jsonl.gz`): SPACE or P pause, 1-4 speed, N step, R restart, T trail, H lines |
| `make runs` | List all experiment runs (newest first): driver, stage, rules, reward, episodes, mean and best score, survival |
| `make run_heuristic` | Run the heuristic for 100 episodes, headless, into `runs/` |
| `make run_random` | Same, with the random baseline |
| `make run_driver DRIVER=name` | Run any headless driver (`random`, `heuristic`, `agent:<id>`) |
| `make run_episodes EPISODES=n` | Heuristic, `n` episodes |
| `make run_reward REWARD=name` | Heuristic, with another reward profile |
| `make run_rules RULES=name` | Heuristic, with other game rules |
| `make run_stage STAGE=name` | Heuristic, on another stage |
| `make run_seconds SECONDS=n` | Heuristic, with another round length |
| `make run_best RUN=folder` | Watch a run's best replay |
| `make new_agent AGENT=id` | Create an untrained agent in `agents/<id>/` from `models/small.json` |
| `make maze_car_agent AGENT=id` | Watch an agent drive (its best scored checkpoint, else its newest) |
| `make run_agent AGENT=id` | Run an agent for 100 episodes, headless, into `runs/` |
| `make train AGENT=id` | Train an agent for one phase with `trainers/default.json` (2M decisions, about 7 min). Checkpoints go to `agents/<id>/checkpoints/`, the learning curve to a `runs/` folder. Ctrl+C stops and keeps the weights. Another trainer: `python app.py -train <id> --trainer <name>` |
| `make resume RUN=folder` | Resume a stopped training run exactly, with its own trainer, stage, rules, and reward |
| `make eval AGENT=id` | Score an agent's checkpoints with the evaluation suite (`suites/box.json`), shown next to the baselines, best marked. Watching the agent then uses the best one |
| `make eval_baselines` | Score the heuristic and random baselines only |
| `make agents` | List every agent: model, decisions, best checkpoint and score, milestone, last update |
| `make dataset` | Preview your recordings as an imitation dataset (`datasets/mine.json`): rounds, samples, your mean score, and skipped recordings with why |
| `make imitate AGENT=id` | Clone your driving into an agent (created if new) with `trainers/imitate.json`, then score the clone. Continue with RL: `make train AGENT=id` |
| `make showcase AGENT=id` | Watch an agent's progression: highlight checkpoints on the same round, each after a title card (decisions, training time, suite scores, badges) that stays until Enter. Each round's result also waits for Enter. SPACE or P pause, 1-4 speed, Left/Right checkpoint, R restart, Esc quit |
| `make showcase_all AGENT=id` | The same, for every scored checkpoint |
| `make agent AGENT=id` | An agent's digest: lineage, best scores next to the heuristic, score trend, totals, milestone |
| `make resume_last` | Resume the newest stopped training run |
| `make test` | Run all tests |
| `make test_file FILE=path` | Run one test file |
| `make fixtures` | Regenerate the behavior fixtures (only for an intended behavior change) |
| `make main` | Agent entry point (stub: `src/main.py` prints "Done."). It was `make run` before step 4h |

A missing parameter stops with an example, for example `make replay` → "FILE is required, e.g. make replay FILE=path/to/replay.jsonl". Play commands run `clear` first.

Behind them, `app.py` takes these flags: `-demo maze_car`, `-replay <file>`, `-run <name>`, `-list_runs`, `-best_replay <folder>`, `-list_recordings`, `-replay_last`, `-new_agent <id>`, `--model` (for a new agent, default `small`), `-train <id>`, `--trainer` (default `default`), `-resume <folder>`, `-resume_last`, `--from <agent>@<checkpoint>` (with `-new_agent`: branch a new agent from a checkpoint), `-eval <id>`, `-eval_baselines`, `--suite` (default `box`), `-list_agents`, `-show_agent <id>`, `-preview_dataset`, `-imitate <id>`, `-showcase <id>`, `--showcase_all`, `-control`, `--dataset` (default `mine`), `--imitation_trainer` (default `imitate`), `--norecord`, `--driver`, `--player`, `--reward`, `--stage`, `--rules`, `--episodes`, `--seed` (first seed of a run), `--round_seconds`, plus any config key (below, for example `--maze_car.rules=sprint`).

## Config overrides

Config uses absl flags with `ml_collections` `ConfigDict`s (`maze_car`, `agent`), defined in `src/config.py`. Override values from the command line:

```
python app.py -demo maze_car --maze_car.show_collision_distance=False
```

## Tests

`pytest.ini` sets `-p no:warnings -rs -v -l`. `app.py --tests` still only prints a TODO. Use `make test` or `pytest`.

```
pytest                                                          # all
pytest "tests/test_behavior.py::test_scenario_matches_fixture[mixed]"   # single test
```

### Behavior tests

These pin down the current car physics exactly (roadmap step 1). They're the safety net for the ECS refactor.

| File | Role |
|---|---|
| `tests/scenarios.py` | Scripted action sequences. Implementation-neutral |
| `tests/fixtures/behavior/*.json` | Expected car state after every step (center, angle, speed, pedal, steering, ray distances), one line per step |
| `tests/harness.py` | Two runners over the same scenarios: `run_world` (the simulation directly) and `run_env` (through `MazeCarEnv.game_step`, headless). Both must match the fixtures |
| `tests/test_behavior.py` | Compares every runner against the fixtures exactly, and checks determinism |

The fixtures were first recorded from the pre-ECS code, which the ECS matched exactly (step 2b). They were regenerated for the realistic controls (step 3b), and will be again for each intended behavior change.

`tests/test_controls.py` checks the driving design targets directly (for example "coasting from max speed stops in about 3 s"), so a wrong physics value fails with a clear message rather than just a fixture mismatch.

Regenerate the fixtures **only** for an intended behavior change. The generator uses `run_world`:

```
python -m tests.generate_behavior_fixtures
```

## Lint

`.flake8` sets max line length 80 and ignores E501. `.pylintrc` disables docstring and a few other checks. Neither flake8 nor pylint is in `requirements.txt`, so install them separately if needed.
