from absl import app
from ml_collections import config_flags

from src.config import get_agent_config, get_fast_traffic_config
from src.main import Main


def run(_):
    Main()


if __name__ == "__main__":
    config_flags.DEFINE_config_dict("agent", get_agent_config())
    config_flags.DEFINE_config_dict("fast_traffic", get_fast_traffic_config())

    app.run(run)
