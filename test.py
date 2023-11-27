import pytest
from absl import app
from ml_collections import ConfigDict, config_flags


def setup_test_flags():
    config = ConfigDict()

    config.lane_length = 5
    config.spawn_rate = 0.4
    config.total_ticks = 50

    config_flags.DEFINE_config_dict("fast_traffic", config)


def test_all(_):
    pytest.main()


if __name__ == "__main__":
    setup_test_flags()
    app.run(test_all)
