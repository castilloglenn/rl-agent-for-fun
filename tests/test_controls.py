"""Checks the realistic driving controls against docs/game-design.md."""

import pytest

from src.config import get_maze_car_config
from src.sim.components import ActionInput, CarSpec, Pedal
from src.sim.factories import _car_spec
from src.sim.resources import SimConfig
from src.sim.systems.movement import next_speed
from src.sim.systems.steering import turn_step

FPS = get_maze_car_config().sim.steps_per_second
GAS = ActionInput(gas=True)
REVERSE = ActionInput(reverse=True)
BRAKE = ActionInput(brake=True)
NONE = ActionInput()


@pytest.fixture
def spec() -> CarSpec:
    return _car_spec(SimConfig.from_config(get_maze_car_config()))


def _steps_until(speed, action, spec, done) -> int:
    for steps in range(1, 10_000):
        speed, _ = next_speed(speed, action, spec)
        if done(speed):
            return steps
    raise AssertionError("never finished")


def test_gas_reaches_max_speed_in_about_1_5_seconds(spec):
    steps = _steps_until(0.0, GAS, spec, lambda s: s >= spec.max_speed)
    assert steps / FPS == pytest.approx(1.5, abs=0.02)


def test_speed_never_exceeds_limits(spec):
    speed = 0.0
    for _ in range(1000):
        speed, _ = next_speed(speed, GAS, spec)
    assert speed == spec.max_speed
    for _ in range(1000):
        speed, _ = next_speed(speed, REVERSE, spec)
    assert speed == -spec.max_reverse_speed


def test_coasting_from_max_speed_stops_in_about_3_seconds(spec):
    steps = _steps_until(spec.max_speed, NONE, spec, lambda s: s == 0)
    assert steps / FPS == pytest.approx(3.0, abs=0.02)


def test_holding_brake_from_max_speed_stops_in_about_0_5_seconds(spec):
    steps = _steps_until(spec.max_speed, BRAKE, spec, lambda s: s == 0)
    assert steps / FPS == pytest.approx(0.5, abs=0.02)


def test_brake_taps_slow_down_without_stopping(spec):
    speed = spec.max_speed
    for _ in range(3):
        for _ in range(6):
            speed, pedal = next_speed(speed, BRAKE, spec)
            assert pedal == Pedal.BRAKING
        for _ in range(24):
            speed, pedal = next_speed(speed, NONE, spec)
            assert pedal == Pedal.COASTING
    assert 0 < speed < spec.max_speed


def test_reverse_while_moving_forward_brakes_before_reversing(spec):
    speed = spec.max_speed
    speeds, pedals = [], []
    for _ in range(200):
        speed, pedal = next_speed(speed, REVERSE, spec)
        speeds.append(speed)
        pedals.append(pedal)

    first_negative = next(i for i, s in enumerate(speeds) if s < 0)
    assert speeds[first_negative - 1] == 0.0  # passes through a full stop
    assert set(pedals[:first_negative]) == {Pedal.BRAKING}
    assert set(pedals[first_negative:]) == {Pedal.REVERSE}


def test_gas_while_rolling_backward_brakes_first(spec):
    speed, pedal = next_speed(-spec.max_reverse_speed, GAS, spec)
    assert pedal == Pedal.BRAKING
    assert -spec.max_reverse_speed < speed <= 0


def test_brake_beats_gas_and_gas_beats_reverse(spec):
    _, pedal = next_speed(1.0, ActionInput(gas=True, brake=True), spec)
    assert pedal == Pedal.BRAKING
    _, pedal = next_speed(0.0, ActionInput(gas=True, reverse=True), spec)
    assert pedal == Pedal.GAS


def test_idle_car_stays_idle(spec):
    assert next_speed(0.0, NONE, spec) == (0.0, Pedal.IDLE)


def test_stopped_car_cannot_turn(spec):
    assert turn_step(ActionInput(turn_left=True), 0.0, spec) == 0


def test_turn_rate_follows_speed_up_to_the_max(spec):
    left = ActionInput(turn_left=True)
    slow = turn_step(left, spec.full_turn_speed / 4, spec)
    full = turn_step(left, spec.full_turn_speed, spec)
    fast = turn_step(left, spec.max_speed, spec)

    assert 0 < slow < full
    assert full == fast == pytest.approx(240 / FPS)  # 240 degrees/s


def test_steering_flips_while_reversing(spec):
    left = ActionInput(turn_left=True)
    assert turn_step(left, 1.0, spec) > 0
    assert turn_step(left, -1.0, spec) < 0


def test_left_and_right_together_cancel(spec):
    both = ActionInput(turn_left=True, turn_right=True)
    assert turn_step(both, spec.max_speed, spec) == 0
