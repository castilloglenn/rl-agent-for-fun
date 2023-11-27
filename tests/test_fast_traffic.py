from tf_agents.environments.utils import validate_py_environment
from tf_agents.utils import test_utils

from src.environments.fast_traffic import FastTrafficEnv


class FastTrafficEnvTest(test_utils.TestCase):
    def test_integrity(self):
        env = FastTrafficEnv()
        validate_py_environment(env)
        self.assertIsInstance(env, FastTrafficEnv)
