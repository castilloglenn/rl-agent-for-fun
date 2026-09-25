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

    # World coordinates. The origin offset is a leftover from when the field
    # was placed relative to a 900x600 window; it keeps the physics fixtures
    # unchanged. The window size is derived from the field and panel layout.
    config.field = ConfigDict()
    config.field.x = 22.5
    config.field.y = 97.5
    config.field.width = 855.0
    config.field.height = 480.0

    config.display = ConfigDict()
    config.display.fps = 90

    config.sensors = ConfigDict()
    config.sensors.ray_length = 1800

    config.car = ConfigDict()
    config.car.width = 24
    config.car.height = 16
    config.car.acceleration_unit = 0.25
    config.car.acceleration_max = 2.0

    return config
