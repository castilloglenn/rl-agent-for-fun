import numpy as np
from absl import flags
from tf_agents.environments import utils

from src.environments.fast_traffic import FastTrafficEnv
from src.helpers import print_spaced

FLAGS = flags.FLAGS
print = print_spaced  # Temporary


class Main:
    def __init__(self):
        environment = FastTrafficEnv()
        utils.validate_py_environment(environment=environment)

        get_new_card_action = np.array(0, dtype=np.int32)
        end_round_action = np.array(1, dtype=np.int32)

        environment = FastTrafficEnv()
        time_step = environment.reset()
        print(time_step)
        cumulative_reward = time_step.reward

        for _ in range(3):
            time_step = environment.step(get_new_card_action)
            print(time_step)
            cumulative_reward += time_step.reward

        time_step = environment.step(end_round_action)
        print(time_step)
        cumulative_reward += time_step.reward
        print("Final Reward = ", cumulative_reward)

        print("Done.")
