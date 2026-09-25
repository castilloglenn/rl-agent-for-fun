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
| `make maze_car` | Drive with the keyboard: WASD/arrows, SPACE brakes, R restarts, H toggles lines, Esc quits |
| `make maze_car_heuristic` | Watch the heuristic baseline drive |
| `make maze_car_random` | Watch the random baseline drive |
| `make maze_car_driver DRIVER=name` | Any driver: `keyboard`, `random`, `heuristic` |
| `make maze_car_player PLAYER=name` | Drive with your player name (HUD, and recordings from 4h) |
| `make maze_car_stage STAGE=name` | Another stage: a name in `stages/`, or a path |
| `make maze_car_reward REWARD=name` | Another reward profile: a name in `rewards/`, or a path |
| `make maze_car_seconds SECONDS=n` | Another round length |
| `make maze_car_fps FPS=n` | Cap the frame rate (0 = match the display) |
| `make replay FILE=path` | Watch a replay (`.jsonl` or `.jsonl.gz`): SPACE pause, 1-4 speed, N step, R restart |
| `make test` | Run all tests |
| `make test_file FILE=path` | Run one test file |
| `make fixtures` | Regenerate the behavior fixtures (only for an intended behavior change) |
| `make run` | Agent entry point (stub: `src/main.py` prints "Done.") |

A missing parameter stops with an example, for example `make replay` → "FILE is required, e.g. make replay FILE=path/to/replay.jsonl". Play commands run `clear` first.

Behind them, `app.py` takes these flags: `-demo maze_car`, `-replay <file>`, `--driver`, `--player`, `--reward`, plus any config key (below).

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
