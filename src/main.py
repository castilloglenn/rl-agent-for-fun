from __future__ import absolute_import, division, print_function

import keras
import tensorflow as tf
from absl import flags
from tf_agents.agents.dqn import dqn_agent
from tf_agents.environments import tf_py_environment
from tf_agents.networks import sequential
from tf_agents.utils import common

from src.environments.fast_traffic import FastTrafficEnv
from src.helpers import dense_layer, print_spaced

FLAGS = flags.FLAGS
print = print_spaced  # Temporary


class Main:
    def __init__(self):
        train_env = tf_py_environment.TFPyEnvironment(FastTrafficEnv())
        # test_env = tf_py_environment.TFPyEnvironment(FastTrafficEnv())

        time_step_spec = train_env.time_step_spec()
        action_spec = train_env.action_spec()
        num_actions = action_spec.maximum - action_spec.minimum + 1

        fc_layers = FLAGS.agent.fully_connected_layers
        dense_layers = [dense_layer(num_units) for num_units in fc_layers]
        q_values_layer = keras.layers.Dense(
            units=num_actions,
            activation=None,
            kernel_initializer=keras.initializers.RandomUniform(),
            bias_initializer=keras.initializers.Constant(-0.2),
        )
        q_net = sequential.Sequential(dense_layers + [q_values_layer])

        learning_rate = FLAGS.agent.learning_rate
        optimizer = keras.optimizers.legacy.Adam(learning_rate=learning_rate)
        train_step_counter = tf.Variable(0)
        agent = dqn_agent.DqnAgent(
            time_step_spec=time_step_spec,
            action_spec=action_spec,
            q_network=q_net,
            optimizer=optimizer,
            td_errors_loss_fn=common.element_wise_squared_loss,
            train_step_counter=train_step_counter,
        )
        agent.initialize()

        print("Done.")
