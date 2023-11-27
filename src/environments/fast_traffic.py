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
        return ts.restart(self._parse_observation())

    def _step(self, action):
        return self._next_frame(action)

    # """ Inner Game Mechanics """

    def _init_game(self):
        self._cars = np.zeros(
            [2, FLAGS.fast_traffic.lane_length],
            dtype=np.int32,
        )
        self._player = np.int32(random.choice([0, 1]))
        self._ticks = 0

    def _parse_observation(self) -> np.ndarray[np.ndarray[np.int32]]:
        observation = self._cars.copy()
        observation[self._player, 0] = 2
        return observation

    def _try_spawn_car(self, chance=None):
        if chance is None:
            chance = random.random()

        if chance > FLAGS.fast_traffic.spawn_rate:
            return None

        lane = random.choice([0, 1])
        self._cars[lane][-1] = 1

    def _move_cars(self):
        self._cars[:, 0] = 0
        self._cars = np.roll(self._cars, shift=-1)

    def _check_collision(self) -> bool:
        return bool(self._cars[self._player][0])

    def _apply_action(self, action):
        if action == 1:
            return None

        self._player = int(not bool(self._player))

    def _next_frame(self, action):
        if self._ticks >= FLAGS.fast_traffic.total_ticks:
            return self.reset()

        self._apply_action(action=action)
        if self._check_collision():
            return ts.termination(
                observation=self._parse_observation(), reward=self._ticks
            )

        self._move_cars()
        self._try_spawn_car()
        self._ticks += 1

        return ts.transition(
            observation=self._parse_observation(),
            reward=self._ticks,
        )
