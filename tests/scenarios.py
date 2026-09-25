"""Scripted action sequences for the behavior tests.

Each action is (turn_left, turn_right, gas, reverse, brake).
Changing a scenario requires regenerating its fixture.
"""

NONE = (False, False, False, False, False)
LEFT = (True, False, False, False, False)
RIGHT = (False, True, False, False, False)
GAS = (False, False, True, False, False)
REVERSE = (False, False, False, True, False)
BRAKE = (False, False, False, False, True)
GAS_LEFT = (True, False, True, False, False)
GAS_RIGHT = (False, True, True, False, False)
REVERSE_LEFT = (True, False, False, True, False)
REVERSE_RIGHT = (False, True, False, True, False)
LEFT_RIGHT = (True, True, False, False, False)
GAS_REVERSE = (False, False, True, True, False)
GAS_BRAKE = (False, False, True, False, True)
BRAKE_LEFT = (True, False, False, False, True)


def _seq(*parts: tuple[tuple, int]) -> list[tuple]:
    return [action for action, count in parts for _ in range(count)]


SCENARIOS: dict[str, list[tuple]] = {
    "idle": _seq((NONE, 30)),
    "forward": _seq((GAS, 150)),
    # A stopped car can't turn.
    "turn_in_place": _seq((LEFT, 60), (RIGHT, 30)),
    "turn_left_moving": _seq((GAS, 30), (GAS_LEFT, 120)),
    "turn_right_moving": _seq((GAS, 30), (GAS_RIGHT, 120)),
    "reverse_turning": _seq((REVERSE_LEFT, 60), (REVERSE_RIGHT, 60)),
    "border_clamp": _seq((GAS, 400)),
    "circle_to_max_acceleration": _seq((GAS_LEFT, 400)),
    "coast_to_stop": _seq((GAS, 90), (NONE, 200)),
    "brake_hold": _seq((GAS, 120), (BRAKE, 60)),
    "brake_taps": _seq((GAS, 120), *[(BRAKE, 6), (NONE, 24)] * 4),
    "reverse_brakes_first": _seq((GAS, 90), (REVERSE, 150)),
    "gas_brakes_reverse": _seq((REVERSE, 120), (GAS, 60)),
    "mixed": _seq(
        (GAS, 40),
        (NONE, 10),
        (GAS_RIGHT, 45),
        (GAS, 60),
        (LEFT_RIGHT, 10),
        (GAS_REVERSE, 20),
        (BRAKE_LEFT, 15),
        (REVERSE, 30),
        (GAS_LEFT, 90),
        (GAS_BRAKE, 10),
        (REVERSE_RIGHT, 25),
        (GAS, 150),
    ),
}
