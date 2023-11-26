from ml_collections import ConfigDict


def get_agent_config() -> ConfigDict:
    config = ConfigDict()

    config.num_iterations = 20000

    config.initial_collect_steps = 100
    config.collect_steps_per_iteration = 1

    config.batch_size = 64
    config.learning_rate = 1e-3
    config.log_interval = 200

    config.num_eval_episodes = 10
    config.eval_interval = 1000

    return config


def get_fast_traffic_config() -> ConfigDict:
    config = ConfigDict()

    config.lane_length = 5
    config.spawn_rate = 0.25

    return config
