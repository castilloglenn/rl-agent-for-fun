from absl import flags
from ml_collections import ConfigDict

flags.DEFINE_boolean("tests", False, "Run unit tests.")
flags.DEFINE_string("demo", "", "Run games with human inputs.")


def get_agent_config() -> ConfigDict:
    config = ConfigDict()

    return config


def get_maze_car_config() -> ConfigDict:
    config = ConfigDict()
    config.show_bounds: bool = True

    config.window = ConfigDict()
    config.window.title: str = "Maze Car"
    config.window.width: int = 640
    config.window.height: int = 480

    config.display = ConfigDict()
    config.display.fps: int = 60

    config.car = ConfigDict()
    config.car.width: int = 24
    config.car.height: int = 16
    config.car.acceleration_unit: float = 10.0
    config.car.acceleration_max: float = 2.5

    return config
