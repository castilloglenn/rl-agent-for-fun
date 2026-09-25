"""Scripted action sequences for the behavior tests.

Each action is (turn_left, turn_right, move_forward, move_backward).
Changing a scenario requires regenerating its fixture.
"""

NONE = (False, False, False, False)
LEFT = (True, False, False, False)
RIGHT = (False, True, False, False)
FORWARD = (False, False, True, False)
BACKWARD = (False, False, False, True)
FORWARD_LEFT = (True, False, True, False)
FORWARD_RIGHT = (False, True, True, False)
BACKWARD_LEFT = (True, False, False, True)
BACKWARD_RIGHT = (False, True, False, True)
LEFT_RIGHT = (True, True, False, False)
FORWARD_BACKWARD = (False, False, True, True)


def _seq(*parts: tuple[tuple, int]) -> list[tuple]:
    return [action for action, count in parts for _ in range(count)]


SCENARIOS: dict[str, list[tuple]] = {
    "idle": _seq((NONE, 30)),
    "forward": _seq((FORWARD, 150)),
    "turn_in_place": _seq((LEFT, 60), (RIGHT, 30)),
    "turn_left_moving": _seq((FORWARD, 30), (FORWARD_LEFT, 120)),
    "turn_right_moving": _seq((FORWARD, 30), (FORWARD_RIGHT, 120)),
    "reverse_turning": _seq((BACKWARD_LEFT, 60), (BACKWARD_RIGHT, 60)),
    "border_clamp": _seq((FORWARD, 300)),
    "circle_to_max_acceleration": _seq((FORWARD_LEFT, 400)),
    "mixed": _seq(
        (FORWARD, 40),
        (NONE, 10),
        (FORWARD_RIGHT, 45),
        (FORWARD, 60),
        (LEFT_RIGHT, 10),
        (FORWARD_BACKWARD, 20),
        (BACKWARD, 30),
        (FORWARD_LEFT, 90),
        (BACKWARD_RIGHT, 25),
        (FORWARD, 150),
    ),
}
