from ml_collections import ConfigDict


def get_config() -> ConfigDict:
    config = ConfigDict()

    config.num_iterations = 20000  # @param {type:"integer"}

    config.initial_collect_steps = 100  # @param {type:"integer"}
    config.collect_steps_per_iteration = 1  # @param {type:"integer"}

    config.batch_size = 64  # @param {type:"integer"}
    config.learning_rate = 1e-3  # @param {type:"number"}
    config.log_interval = 200  # @param {type:"integer"}

    config.num_eval_episodes = 10  # @param {type:"integer"}
    config.eval_interval = 1000  # @param {type:"integer"}

    return config
