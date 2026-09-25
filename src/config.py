from absl import flags
from ml_collections import ConfigDict

flags.DEFINE_boolean("tests", False, "Run unit tests.")
flags.DEFINE_string("demo", "", "Run games with human inputs.")
flags.DEFINE_string("replay", "", "Play a replay file in the window.")
flags.DEFINE_string(
    "driver", "keyboard", "Who drives the demo: keyboard, random, heuristic."
)
flags.DEFINE_string("player", "You", "Your player name (recordings, HUD).")
flags.DEFINE_string(
    "reward", "default", "Reward profile: a name in rewards/, or a path."
)


# Every top-level maze_car key is one of these (tests/test_config.py checks).
# Game-defining keys change what happens in a game, so replays and runs save
# them. Presentation keys only change how it looks, and are never saved.
# See docs/decisions/010-decouple-before-file-formats.md.
GAME_KEYS = (
    "sim",
    "stage",
    "car",
    "sensors",
    "round",
    "game",
    "rewards",
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
    config.update(game)
    return config


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

    # Rounds and games. See docs/game-design.md.
    config.round = ConfigDict()
    config.round.seconds = 60.0
    config.game = ConfigDict()
    config.game.rounds = 1
    config.game.seed = 0  # checkpoint spawns; the demo picks a new one per R

    config.rewards = ConfigDict()
    config.rewards.distance_step = 10.0  # px driven forward per +1 point
    config.rewards.checkpoint = 100

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
