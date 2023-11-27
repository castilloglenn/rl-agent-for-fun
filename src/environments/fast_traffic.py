import random

import numpy as np
from absl import flags
from tf_agents.environments import py_environment
from tf_agents.specs.array_spec import BoundedArraySpec
from tf_agents.trajectories import time_step as ts

FLAGS = flags.FLAGS


class FastTrafficEnv(py_environment.PyEnvironment):
    def __init__(self):
        super().__init__()
        self._action_spec = BoundedArraySpec(
            shape=(), dtype=np.int32, minimum=0, maximum=1, name="action"
        )
        self._observation_spec = BoundedArraySpec(
            shape=(2, FLAGS.fast_traffic.lane_length),
            dtype=np.int32,
            minimum=0,
            maximum=2,
            name="observation",
        )
        self._init_game()

    def action_spec(self):
        return self._action_spec

    def observation_spec(self):
        return self._observation_spec

    def _reset(self):
        self._init_game()
        return ts.restart(self.parse_observation())

    def _step(self, action):
        return self.next_frame(action)

    # """ Inner Game Mechanics """

    def _init_game(self):
        self.cars = np.zeros(
            [2, FLAGS.fast_traffic.lane_length],
            dtype=np.int32,
        )
        self.player = np.int32(random.choice([0, 1]))
        self.ticks = 0

    def parse_observation(self) -> np.ndarray[np.ndarray[np.int32]]:
        observation = self.cars.copy()
        observation[self.player, 0] = 2
        return observation

    def try_spawn_car(self, chance=None):
        if chance is None:
            chance = random.random()

        if chance > FLAGS.fast_traffic.spawn_rate:
            return None

        lane = random.choice([0, 1])
        self.cars[lane][-1] = 1

    def move_cars(self):
        self.cars[:, 0] = 0
        self.cars = np.roll(self.cars, shift=-1)

    def check_collision(self) -> bool:
        return bool(self.cars[self.player][0])

    def apply_action(self, action):
        if action == 1:
            return None

        self.player = int(not bool(self.player))

    def next_frame(self, action):
        if self.ticks >= FLAGS.fast_traffic.total_ticks:
            return self.reset()

        self.apply_action(action=action)
        if self.check_collision():
            return ts.termination(
                observation=self.parse_observation(), reward=self.ticks
            )

        self.move_cars()
        self.try_spawn_car()
        self.ticks += 1

        return ts.transition(
            observation=self.parse_observation(),
            reward=self.ticks,
        )
