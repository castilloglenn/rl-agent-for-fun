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
| `make test` | `python app.py --tests` | Stub. Prints a TODO |

Every `make` target runs `clear` first.

## Config overrides

Config uses absl flags with `ml_collections` `ConfigDict`s (`maze_car`, `agent`), defined in `src/config.py`. Override values from the command line:

```
python app.py -demo maze_car --maze_car.show_collision_distance=False
```

## Tests

`pytest.ini` sets `-p no:warnings -rs -v -l`. `tests/` has no tests yet.

```
pytest                                # all
pytest tests/test_x.py::test_name     # single test
```

Env classes read global `FLAGS.maze_car`, so a test must define and parse the flags before building them. See [architecture](architecture.md#config).

## Lint

`.flake8` sets max line length 80 and ignores E501. `.pylintrc` disables docstring and a few other checks. Neither flake8 nor pylint is in `requirements.txt`, so install them separately if needed.
