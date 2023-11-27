from ml_collections import ConfigDict


def get_agent_config() -> ConfigDict:
    config = ConfigDict()

    config.fully_connected_layers: tuple[*int] = (100, 50)

    config.num_iterations: int = 20_000

    config.initial_collect_steps: int = 100
    config.collect_steps_per_iteration: int = 1

    config.max_buffer_size: int = 1_000
    config.batch_size: int = 64
    config.learning_rate: float = 1e-3
    config.log_interval: int = 200

    config.num_eval_episodes: int = 10
    config.eval_interval: int = 1_000

    return config


def get_fast_traffic_config() -> ConfigDict:
    config = ConfigDict()

    config.lane_length: int = 5
    config.spawn_rate: float = 0.4
    config.total_ticks: int = 50

    return config
