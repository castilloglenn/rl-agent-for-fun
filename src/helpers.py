import keras


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
