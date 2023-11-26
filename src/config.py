from ml_collections import ConfigDict


def get_config() -> ConfigDict:
    config = ConfigDict()

    config.test = ConfigDict()
    config.test.a = "config test"

    return config
