"""The 12 canonical actions: steering x pedal.

The simulation resolves input priorities (left + right cancel, and brake
beats gas beats reverse), so every one of the 32 combinations of the 5 keys
behaves exactly like one of these 12. See
docs/decisions/012-agent-training-modes.md.
"""

Action = tuple[bool, bool, bool, bool, bool]  # env.action_names order

STEERING = ("left", "none", "right")
PEDALS = ("none", "gas", "reverse", "brake")

_STEER_KEYS = {
    "left": (True, False),
    "none": (False, False),
    "right": (False, True),
}
_PEDAL_KEYS = {
    "none": (False, False, False),
    "gas": (True, False, False),
    "reverse": (False, True, False),
    "brake": (False, False, True),
}

CANONICAL_ACTIONS: tuple[Action, ...] = tuple(
    _STEER_KEYS[steer] + _PEDAL_KEYS[pedal]
    for steer in STEERING
    for pedal in PEDALS
)
CANONICAL_NAMES: tuple[str, ...] = tuple(
    f"{steer}+{pedal}" for steer in STEERING for pedal in PEDALS
)


def canonical_index(action: Action) -> int:
    """The canonical action that behaves exactly like `action`."""
    turn_left, turn_right, gas, reverse, brake = (bool(a) for a in action)
    steer = "left" if turn_left and not turn_right else (
        "right" if turn_right and not turn_left else "none"
    )
    if brake:
        pedal = "brake"
    elif gas:
        pedal = "gas"
    elif reverse:
        pedal = "reverse"
    else:
        pedal = "none"
    return STEERING.index(steer) * len(PEDALS) + PEDALS.index(pedal)
