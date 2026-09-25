"""Pins the current car physics. Every value must match exactly.

A failure means behavior changed. During a structure-only refactor that
is a bug; for an intended change, regenerate the fixtures.
"""

import json

import pytest

from tests.generate_behavior_fixtures import FIXTURE_DIR
from tests.harness import RUNNERS, config_snapshot, setup_flags
from tests.scenarios import SCENARIOS


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text())


@pytest.mark.parametrize("runner", sorted(RUNNERS))
@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_scenario_matches_fixture(name, runner):
    setup_flags()
    fixture = _load(name)

    assert config_snapshot() == fixture["config"], "config defaults changed"
    assert [list(a) for a in SCENARIOS[name]] == fixture["actions"], (
        "scenario changed, regenerate its fixture"
    )

    snapshots = RUNNERS[runner](SCENARIOS[name])
    assert len(snapshots) == len(fixture["snapshots"])
    for step, (actual, expected) in enumerate(
        zip(snapshots, fixture["snapshots"])
    ):
        assert actual == expected, f"first mismatch at step {step}"


@pytest.mark.parametrize("runner", sorted(RUNNERS))
def test_runs_are_deterministic(runner):
    actions = SCENARIOS["mixed"]
    assert RUNNERS[runner](actions) == RUNNERS[runner](actions)
