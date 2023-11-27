import keras
import numpy as np
import tensorflow as tf


def print_spaced(*values) -> None:
    double_spaced = "\n\n"
    print(f"{' '.join(map(str, values))}", end=double_spaced)


def dense_layer(num_units):
    return keras.layers.Dense(
        num_units,
        activation=keras.activations.relu,
        kernel_initializer=keras.initializers.VarianceScaling(
            scale=2.0, mode="fan_in", distribution="truncated_normal"
        ),
    )


def compute_avg_return(environment, policy, num_episodes=10):
    total_return = 0.0
    for _ in range(num_episodes):
        time_step = environment.reset()
        episode_return = 0.0

        while not time_step.is_last():
            action_step = policy.action(time_step)
            time_step = environment.step(action_step.action)
            episode_return += time_step.reward
        total_return += episode_return

    avg_return = total_return / num_episodes
    return avg_return.numpy()[0]


def create_batch(sampled_experience):
    states = []
    actions = []
    next_states = []
    rewards = []

    for step in sampled_experience:
        states.append(step.observation)
        actions.append(step.action)
        next_states.append(step.next_step.observation)
        rewards.append(step.reward)

    states_batch = tf.convert_to_tensor(np.array(states), dtype=tf.float32)
    actions_batch = tf.convert_to_tensor(np.array(actions), dtype=tf.int32)
    next_states_batch = tf.convert_to_tensor(
        np.array(next_states),
        dtype=tf.float32,
    )
    rewards_batch = tf.convert_to_tensor(np.array(rewards), dtype=tf.float32)

    return {
        "states": states_batch,
        "actions": actions_batch,
        "next_states": next_states_batch,
        "rewards": rewards_batch,
    }
