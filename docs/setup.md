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

| Command | Runs | Status |
|---|---|---|
| `make maze_car` | `python app.py -demo maze_car` | Works. Human-driven demo: WASD/arrows drive, SPACE brakes, R restarts, H toggles lines, Esc quits |
| `make replay FILE=<path>` | `python app.py -replay <path>` | Works. Plays a replay (`.jsonl` or `.jsonl.gz`): SPACE pause, 1-4 speed, N step, R restart, Esc quits |
| `make run` | `python app.py` | Stub. `src/main.py` `Main` prints "Done." |
| `make test` | `python -m pytest` | Works. Runs all tests |

Every `make` target runs `clear` first.

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
