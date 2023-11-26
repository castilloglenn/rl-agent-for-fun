from absl import flags
from tf_agents.environments import utils

from src.environment import CardGameEnv

FLAGS = flags.FLAGS


class Main:
    def __init__(self):
        environment = CardGameEnv()
        utils.validate_py_environment(environment=environment)

        print("Done.")
