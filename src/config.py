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

    # The simulation runs at a fixed rate, independent of the display.
    # See docs/decisions/008-fixed-timestep-clock.md.
    config.sim = ConfigDict()
    config.sim.steps_per_second = 120

    config.display = ConfigDict()
    config.display.max_fps = 0  # 0 = match the display's refresh rate

    config.sensors = ConfigDict()
    config.sensors.ray_length = 1800

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
