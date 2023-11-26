import numpy as np
from absl import flags
from tf_agents.environments import utils

from src.environment import CardGameEnv
from src.helpers import print_spaced

FLAGS = flags.FLAGS


class Main:
    def __init__(self):
        environment = CardGameEnv()
        utils.validate_py_environment(environment=environment)

        get_new_card_action = np.array(0, dtype=np.int32)
        end_round_action = np.array(1, dtype=np.int32)

        environment = CardGameEnv()
        time_step = environment.reset()
        print_spaced(time_step)
        cumulative_reward = time_step.reward

        for _ in range(3):
            time_step = environment.step(get_new_card_action)
            print_spaced(time_step)
            cumulative_reward += time_step.reward

        time_step = environment.step(end_round_action)
        print_spaced(time_step)
        cumulative_reward += time_step.reward
        print_spaced("Final Reward = ", cumulative_reward)

        print_spaced("Done.")
