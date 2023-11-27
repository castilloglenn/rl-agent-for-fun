from __future__ import absolute_import, division, print_function

import keras
import tensorflow as tf
from absl import flags
from tf_agents.agents.dqn import dqn_agent

# from tf_agents.drivers.py_driver import PyDriver
from tf_agents.environments import tf_py_environment
from tf_agents.networks import sequential

# from tf_agents.policies.py_tf_eager_policy import PyTFEagerPolicy
from tf_agents.specs import tensor_spec
from tf_agents.utils import common

from src.environments.fast_traffic import FastTrafficEnv
from src.helpers import compute_avg_return, dense_layer

FLAGS = flags.FLAGS


class Main:
    def __init__(self):
        env = FastTrafficEnv()
        train_py_env = FastTrafficEnv()
        test_py_env = FastTrafficEnv()

        train_tf_env = tf_py_environment.TFPyEnvironment(train_py_env)
        test_tf_env = tf_py_environment.TFPyEnvironment(test_py_env)

        time_step_spec = train_tf_env.time_step_spec()
        action_spec = tensor_spec.from_spec(env.action_spec())
        num_actions = action_spec.maximum - action_spec.minimum + 1

        fc_layers = FLAGS.agent.fully_connected_layers
        lane_length = FLAGS.fast_traffic.lane_length

        input_layer = keras.layers.Flatten(input_shape=(2, lane_length))
        dense_layers = [dense_layer(num_units) for num_units in fc_layers]
        output_layer = keras.layers.Dense(
            units=num_actions,
            activation=None,
            kernel_initializer=keras.initializers.RandomUniform(),
            bias_initializer=keras.initializers.Constant(-0.2),
        )
        q_net = sequential.Sequential(
            [input_layer] + dense_layers + [output_layer],
        )

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

        agent.train = common.function(agent.train)
        agent.train_step_counter.assign(0)

        num_eval_episodes = FLAGS.agent.num_eval_episodes
        avg_return = compute_avg_return(
            test_tf_env,
            agent.policy,
            num_eval_episodes,
        )
        # returns = [avg_return]
        print(f"Average return before training: {avg_return:,.2f}")

        # time_step = train_py_env.reset()

        # collect_steps_per_iteration = FLAGS.agent.collect_steps_per_iteration
        # collect_driver = PyDriver(
        #     env=env,
        #     policy=PyTFEagerPolicy(
        #         agent.collect_policy,
        #         use_tf_function=True,
        #     ),
        #     observers=[],
        #     max_steps=collect_steps_per_iteration,
        # )

        # experience_buffer = []

        # batch_size = FLAGS.agent.batch_size
        # max_buffer_size = FLAGS.agent.max_buffer_size
        # num_iterations = FLAGS.agent.num_iterations
        # log_interval = FLAGS.agent.log_interval
        # eval_interval = FLAGS.agent.eval_interval

        # for _ in range(num_iterations):
        #     time_step, _ = collect_driver.run(time_step)
        #     experience_buffer.append(time_step)

        #     if len(experience_buffer) > max_buffer_size:
        #         experience_buffer.pop(0)

        #     batch = min(batch_size, len(experience_buffer))
        #     sampled_experience = random.sample(experience_buffer, batch)
        #     tf_batch = create_batch(sampled_experience)
        #     train_loss = agent.train(tf_batch).loss

        #     step = agent.train_step_counter.numpy()
        #     if step % log_interval == 0:
        #         print(f"step = {step}: loss = {train_loss}")

        #     if step % eval_interval == 0:
        #         avg_return = compute_avg_return(
        #             test_tf_env, agent.policy, num_eval_episodes
        #         )
        #         print(f"step = {step}: Average Return = {avg_return}")
        #         returns.append(avg_return)

        print("Done.")
