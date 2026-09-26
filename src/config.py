from absl import flags
from ml_collections import ConfigDict

flags.DEFINE_boolean("tests", False, "Run unit tests.")
flags.DEFINE_string("demo", "", "Run games with human inputs.")
flags.DEFINE_string("replay", "", "Play a replay file in the window.")
flags.DEFINE_string(
    "driver", "keyboard", "Who drives: keyboard, random, heuristic, agent:<id>."
)
flags.DEFINE_string("player", "You", "Your player name (recordings, HUD).")
flags.DEFINE_string(
    "reward", "default", "Reward profile: a name in rewards/, or a path."
)
flags.DEFINE_string("run", "", "Start an experiment run with this name.")
flags.DEFINE_integer("episodes", 100, "Episodes in an experiment run.")
flags.DEFINE_integer(
    "seed", 0, "First seed of a run (episode i uses seed + i)."
)
flags.DEFINE_string("stage", "", "Stage by name or path (default: config).")
flags.DEFINE_string("rules", "", "Rules by name or path (default: config).")
flags.DEFINE_boolean("list_runs", False, "List experiment runs.")
flags.DEFINE_string("new_agent", "", "Create an untrained agent with this id.")
flags.DEFINE_string("model", "small", "Model for a new agent (models/).")
flags.DEFINE_string("train", "", "Train this agent (a training phase).")
flags.DEFINE_string("resume", "", "Resume a stopped training run (folder).")
flags.DEFINE_boolean("resume_last", False, "Resume the newest stopped run.")
flags.DEFINE_string("eval", "", "Score an agent's checkpoints (suite).")
flags.DEFINE_boolean("eval_baselines", False, "Score the baselines (suite).")
flags.DEFINE_string("suite", "box", "Evaluation suite: suites/<name>.json.")
flags.DEFINE_string(
    "from", "", "Branch a new agent from <id>[@checkpoint] (-new_agent)."
)
flags.DEFINE_string(
    "trainer", "default", "Trainer: a name in trainers/, or a path."
)
flags.DEFINE_boolean("record", True, "Record your demo rounds (--norecord).")
flags.DEFINE_boolean("list_recordings", False, "List recorded demo rounds.")
flags.DEFINE_boolean("replay_last", False, "Watch the newest recording.")
flags.DEFINE_string("best_replay", "", "Watch a run's best replay (folder).")
flags.DEFINE_float(
    "round_seconds",
    0.0,
    "Override the rules' round length (renames the rules, e.g. standard-90s).",
)


# Every top-level maze_car key is one of these (tests/test_config.py checks).
# Game-defining keys change what happens in a game, so replays and runs save
# them. Presentation keys only change how it looks, and are never saved.
# See docs/decisions/010-decouple-before-file-formats.md.
GAME_KEYS = (
    "sim",
    "stage",
    "rules",
    "car",
    "sensors",
    "game",
)
PRESENTATION_KEYS = (
    "show_gui",
    "show_bounds",
    "show_collision_distance",
    "window",
    "display",
    "hud",
)


def game_config(config: ConfigDict) -> dict:
    """Only the game-defining part of a maze_car config, as plain data
    (JSON-ready). This is what replays and runs record.
    """
    data = config.to_dict()
    return {key: data[key] for key in GAME_KEYS}


def config_with_game(game: dict, base: ConfigDict | None = None) -> ConfigDict:
    """A saved game-defining part (for example from a replay) applied on
    top of `base` (default: the defaults). Presentation keys stay base's,
    so a replay viewer keeps your HUD settings.
    """
    config = (base or get_maze_car_config()).copy_and_resolve_references()
    _merge_known(config, game)
    return config


def _merge_known(config: ConfigDict, data: dict) -> None:
    """Sets the keys `config` knows, recursively, and skips the rest: old
    replays can hold keys that no longer exist (the flags' config is
    locked, so unknown keys can't be added).
    """
    for key, value in data.items():
        if key not in config:
            continue
        if isinstance(value, dict) and isinstance(config[key], ConfigDict):
            _merge_known(config[key], value)
        else:
            config[key] = value


def get_agent_config() -> ConfigDict:
    config = ConfigDict()

    return config


def get_maze_car_config() -> ConfigDict:
    config = ConfigDict()
    config.show_gui = True
    config.show_bounds = True
    config.show_collision_distance = True

    config.window = ConfigDict()
    config.window.title = "Maze Car"

    # The playing area: a stage file in stages/, by name or path. It holds
    # the size, spawns, and checkpoint rules. See docs/decisions/009.
    config.stage = "box"

    # The simulation runs at a fixed rate, independent of the display.
    # See docs/decisions/008-fixed-timestep-clock.md.
    config.sim = ConfigDict()
    config.sim.steps_per_second = 120

    config.display = ConfigDict()
    config.display.max_fps = 0  # 0 = match the display's refresh rate

    config.sensors = ConfigDict()
    config.sensors.ray_length = 1800

    # How the game is played and scored: a rules file in rules/, by name or
    # path (round length, rounds per game, scoring). See docs/decisions/013.
    config.rules = "standard"
    config.game = ConfigDict()
    config.game.seed = 0  # spawn schedules; the demo picks a new one per R

    # HUD warning colors (amber = caution, red = danger).
    config.hud = ConfigDict()
    config.hud.reaction_time = 0.25  # seconds, for the stopping distance
    config.hud.caution_factor = 2.0  # amber below this x stopping distance
    # Proximity, for all 8 rays in any direction (car is 24 x 16 px).
    config.hud.near_caution = 40.0  # px: amber
    config.hud.near_danger = 15.0  # px: red
    config.hud.fps_caution = 0.9  # amber below this share of the target
    config.hud.fps_danger = 0.5  # red below this share of the target
    config.hud.time_caution = 10.0  # seconds left: amber
    config.hud.time_danger = 5.0  # seconds left: red
    config.hud.checkpoint_near = 80.0  # px: checkpoint distance turns green
    config.hud.hit_flash_seconds = 0.5  # a car blinks red this long after a hit
    config.hud.hit_blink_seconds = 0.1  # on or off this long, while blinking

    config.car = ConfigDict()
    config.car.width = 24
    config.car.height = 16
    # Speeds in px/s, accelerations in px/s². See docs/game-design.md.
    # Calibrated for human play: one reaction time (~0.25 s) at max speed
    # is 75 px, and so is the braking distance.
    config.car.max_speed = 300.0  # crosses the field in ~2.9 s
    config.car.max_reverse_speed = 100.0
    config.car.acceleration = 200.0  # 0 to max speed in 1.5 s
    config.car.reverse_acceleration = 100.0  # 0 to max reverse in 1 s
    config.car.brake_deceleration = 600.0  # max speed to stop in 0.5 s
    config.car.drag = 100.0  # coasting: max speed to stop in 3 s
    config.car.max_turn_rate = 240.0  # degrees/s
    config.car.full_turn_speed = 120.0  # speed where max turn rate is reached
    # Steering wheel: seconds from center to full lock, and back to center.
    config.car.steer_in_time = 0.25
    config.car.steer_return_time = 0.15

    return config
