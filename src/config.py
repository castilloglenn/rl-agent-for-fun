from absl import flags
from ml_collections import ConfigDict

flags.DEFINE_boolean("tests", False, "Run unit tests.")
flags.DEFINE_string("demo", "", "Run games with human inputs.")


def get_agent_config() -> ConfigDict:
    config = ConfigDict()

    config.bool = False

    return config


def get_fast_traffic_config() -> ConfigDict:
    config = ConfigDict()

    return config
