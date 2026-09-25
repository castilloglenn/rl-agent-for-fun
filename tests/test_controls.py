"""Checks the realistic driving controls against docs/game-design.md."""

import pytest

from src.config import get_maze_car_config
from src.sim.components import ActionInput, CarSpec, Pedal
from src.sim.factories import _car_spec
from src.sim.resources import SimConfig
from src.sim.systems.movement import next_speed
from src.sim.systems.steering import next_steering, turn_step

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
    assert turn_step(1.0, 0.0, spec) == 0


def test_turn_rate_follows_speed_up_to_the_max(spec):
    slow = turn_step(1.0, spec.full_turn_speed / 4, spec)
    full = turn_step(1.0, spec.full_turn_speed, spec)
    fast = turn_step(1.0, spec.max_speed, spec)

    assert 0 < slow < full
    assert full == fast == pytest.approx(240 / FPS)  # 240 degrees/s


def test_turn_rate_follows_the_wheel_position(spec):
    half = turn_step(0.5, spec.max_speed, spec)
    full = turn_step(1.0, spec.max_speed, spec)
    assert half == pytest.approx(full / 2)
    assert turn_step(-1.0, spec.max_speed, spec) == pytest.approx(-full)


def test_steering_flips_while_reversing(spec):
    assert turn_step(1.0, 1.0, spec) > 0
    assert turn_step(1.0, -1.0, spec) < 0


# Steering wheel ramp


LEFT = ActionInput(turn_left=True)
RIGHT = ActionInput(turn_right=True)


def _steer(steering, action, spec, steps):
    for _ in range(steps):
        steering = next_steering(steering, action, spec)
    return steering


def _steps_to(steering, action, spec, target) -> int:
    for steps in range(1, 1000):
        steering = next_steering(steering, action, spec)
        if steering == pytest.approx(target, abs=1e-12):
            return steps
    raise AssertionError("never reached")


def test_wheel_reaches_full_lock_in_0_25_seconds(spec):
    assert _steps_to(0.0, LEFT, spec, 1.0) / FPS == pytest.approx(0.25)
    assert _steps_to(0.0, RIGHT, spec, -1.0) / FPS == pytest.approx(0.25)


def test_wheel_self_centers_in_0_15_seconds(spec):
    assert _steps_to(1.0, NONE, spec, 0.0) / FPS == pytest.approx(0.15)
    assert _steps_to(-1.0, NONE, spec, 0.0) / FPS == pytest.approx(0.15)


def test_switching_sides_passes_through_center(spec):
    steering, seen_center = 1.0, False
    for _ in range(int(0.4 * FPS)):
        steering = next_steering(steering, RIGHT, spec)
        seen_center = seen_center or steering == 0.0
    assert seen_center
    assert steering == pytest.approx(-1.0)  # 0.15 s in + 0.25 s out


def test_tap_gives_a_gentle_correction(spec):
    steering = _steer(0.0, LEFT, spec, 6)  # a 50 ms tap
    assert 0 < steering < 0.25


def test_left_and_right_together_recenter(spec):
    both = ActionInput(turn_left=True, turn_right=True)
    assert _steer(1.0, both, spec, int(0.15 * FPS)) == pytest.approx(0.0)


def test_wheel_turns_even_when_stopped(spec):
    """You can turn the wheel while stopped; the car just doesn't rotate."""
    steering = _steer(0.0, LEFT, spec, 30)
    assert steering == pytest.approx(1.0)
    assert turn_step(steering, 0.0, spec) == 0
