import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest  # noqa: E402

from src.config import get_maze_car_config  # noqa: E402
from src.sim.components import ActionInput, Transform  # noqa: E402
from src.sim.factories import create_start_car, create_world  # noqa: E402
from src.utils.common import lerp, lerp_angle  # noqa: E402
from src.utils.timing import FixedStepClock  # noqa: E402

SPS = 120


@pytest.mark.parametrize("display_hz", [60, 90, 120, 144, 240])
def test_one_second_is_120_steps_at_any_display_rate(display_hz):
    clock = FixedStepClock(SPS)
    steps = sum(clock.advance(1 / display_hz) for _ in range(display_hz))
    assert steps in (SPS - 1, SPS)  # float rounding may defer the last one
    assert 0 <= clock.alpha < 1


def test_steps_per_frame_even_on_60_and_120_hz():
    for display_hz, expected in ((60, 2), (120, 1)):
        clock = FixedStepClock(SPS)
        clock.advance(0.5 / SPS)  # start mid-step, away from rounding edges
        counts = {clock.advance(1 / display_hz) for _ in range(600)}
        assert counts == {expected}


def test_stall_skips_backlog_instead_of_catching_up():
    clock = FixedStepClock(SPS, max_steps_per_frame=8)
    assert clock.advance(2.0) == 8
    assert clock.alpha == 0


def test_same_inputs_give_same_world_at_any_display_rate():
    """Frame timing decides how many steps run, never what they do."""

    def drive(display_hz: int) -> tuple:
        world = create_world(get_maze_car_config())
        car = create_start_car(world)
        clock = FixedStepClock(SPS)
        steps_done = 0
        while steps_done < 240:
            for _ in range(clock.advance(1 / display_hz)):
                if steps_done == 240:
                    break
                action = ActionInput(gas=True, turn_left=steps_done > 100)
                world.add_component(car, action)
                world.step()
                steps_done += 1
        transform = world.component(car, Transform)
        return (transform.x, transform.y, transform.angle)

    assert drive(60) == drive(144) == drive(240)


def test_lerp():
    assert lerp(10, 20, 0) == 10
    assert lerp(10, 20, 0.25) == 12.5
    assert lerp(10, 20, 1) == 20


def test_lerp_angle_takes_the_short_way():
    assert lerp_angle(350, 10, 0.5) == pytest.approx(0)
    assert lerp_angle(10, 350, 0.5) == pytest.approx(0)
    assert lerp_angle(90, 180, 0.5) == pytest.approx(135)
    assert lerp_angle(0, 0, 0.7) == 0
