from absl import flags
from ml_collections import ConfigDict

flags.DEFINE_boolean("tests", False, "Run unit tests.")
flags.DEFINE_string("demo", "", "Run games with human inputs.")


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
    config.window.width = 900
    config.window.height = 600

    config.display = ConfigDict()
    config.display.fps = 90

    config.car = ConfigDict()
    config.car.width = 24
    config.car.height = 16
    config.car.acceleration_unit = 0.25
    config.car.acceleration_max = 2.0

    return config
