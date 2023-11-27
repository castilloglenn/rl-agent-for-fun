import numpy as np
from absl import flags
from numpy.testing import assert_array_equal
from tf_agents.environments.utils import validate_py_environment
from tf_agents.policies import random_py_policy
from tf_agents.trajectories.time_step import StepType, TimeStep
from tf_agents.utils import test_utils

from src.environments.fast_traffic import FastTrafficEnv

FLAGS = flags.FLAGS


class FastTrafficEnvTest(test_utils.TestCase):
    def test_integrity(self):
        env = FastTrafficEnv()
        validate_py_environment(env)
        self.assertIsInstance(env, FastTrafficEnv)

    def test_ticks_reset(self):
        env = FastTrafficEnv()
        self.assertEqual(0, env.ticks)

    def test_observation(self):
        env = FastTrafficEnv()

        expected_observation = np.zeros(
            [2, FLAGS.fast_traffic.lane_length], dtype=np.int32
        )
        expected_observation[env.player, 0] = 2

        assert_array_equal(env.parse_observation(), expected_observation)

    def test_spawn_car(self):
        env = FastTrafficEnv()

        # Zero chance means guaranteed spawn
        env.try_spawn_car(chance=0)

        self.assertIn(1, env.cars[:, -1])

    def test_move_cars(self):
        env = FastTrafficEnv()

        env.try_spawn_car(chance=0)
        env.move_cars()

        self.assertIn(1, env.cars[:, -2])

    def test_in_front_spawned_car(self):
        env = FastTrafficEnv()

        env.try_spawn_car(chance=0)
        for _ in range(FLAGS.fast_traffic.lane_length - 1):
            env.move_cars()

        self.assertIn(1, env.cars[:, 0])

    def test_disappear_spawned_car(self):
        env = FastTrafficEnv()

        env.try_spawn_car(chance=0)
        for _ in range(FLAGS.fast_traffic.lane_length):
            env.move_cars()

        self.assertTrue(np.all(env.cars == 0))

    def test_collision_one_step(self):
        env = FastTrafficEnv()

        self.assertFalse(env.check_collision())

        env.try_spawn_car(chance=0)
        self.assertFalse(env.check_collision())

        lane_length = FLAGS.fast_traffic.lane_length
        if lane_length >= 3:
            env.move_cars()
            self.assertFalse(env.check_collision())

    def test_collision_true(self):
        env = FastTrafficEnv()

        time_step_spec = env.time_step_spec()
        action_spec = env.action_spec()
        random_policy = random_py_policy.RandomPyPolicy(
            time_step_spec=time_step_spec,
            action_spec=action_spec,
        )

        time_step: TimeStep = env.reset()
        self.assertEqual(time_step.step_type, StepType.FIRST)

        while time_step.step_type != StepType.LAST:
            action = random_policy.action(time_step).action
            time_step = env.step(action)

        obs = env.parse_observation()
        self.assertEqual(2, obs[env.player, 0])
        self.assertEqual(1, env.cars[env.player, 0])

    def test_reward(self):
        env = FastTrafficEnv()
        tick_limit = FLAGS.fast_traffic.total_ticks

        time_step_spec = env.time_step_spec()
        action_spec = env.action_spec()
        random_policy = random_py_policy.RandomPyPolicy(
            time_step_spec=time_step_spec,
            action_spec=action_spec,
        )

        for _ in range(10):
            time_step: TimeStep = env.reset()
            self.assertEqual(time_step.step_type, StepType.FIRST)

            while time_step.step_type != StepType.LAST:
                action = random_policy.action(time_step).action
                time_step = env.step(action)

            self.assertTrue(env.ticks <= tick_limit)
