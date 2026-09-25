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
| `make maze_car` | `python app.py -demo maze_car` | Works. Human-driven demo: WASD/arrows drive, Esc quits |
| `make run` | `python app.py` | Stub. `src/main.py` `Main` prints "Done." |
| `make test` | `python -m pytest` | Works. Runs the behavior tests |

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
| `tests/fixtures/behavior/*.json` | Expected car state after every step (rect, angle, speed, acceleration, float carry, 4 rays), one line per step |
| `tests/harness.py` | Two runners over the same scenarios: `run_legacy` (pre-ECS code) and `run_ecs` (`src/sim/`). Both must match the fixtures |
| `tests/test_behavior.py` | Compares every runner against the fixtures exactly, and checks determinism |

`run_legacy` runs pygame headless (`SDL_VIDEODRIVER=dummy`), defines and parses the absl flags, and resets the singletons before each run. `run_ecs` needs none of that. The legacy runner is removed in step 2d.

Regenerate the fixtures **only** for an intended behavior change. The generator uses `run_legacy` until step 2d:

```
python -m tests.generate_behavior_fixtures
```

## Lint

`.flake8` sets max line length 80 and ignores E501. `.pylintrc` disables docstring and a few other checks. Neither flake8 nor pylint is in `requirements.txt`, so install them separately if needed.
