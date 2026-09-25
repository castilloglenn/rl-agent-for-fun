"""Pins the current car physics. Every value must match exactly.

A failure means behavior changed. During a structure-only refactor that
is a bug; for an intended change, regenerate the fixtures.
"""

import json

import pytest

from tests.generate_behavior_fixtures import FIXTURE_DIR
from tests.harness import config_snapshot, run_scenario, setup_flags
from tests.scenarios import SCENARIOS


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text())


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_scenario_matches_fixture(name):
    setup_flags()
    fixture = _load(name)

    assert config_snapshot() == fixture["config"], "config defaults changed"
    assert [list(a) for a in SCENARIOS[name]] == fixture["actions"], (
        "scenario changed, regenerate its fixture"
    )

    snapshots = run_scenario(SCENARIOS[name])
    assert len(snapshots) == len(fixture["snapshots"])
    for step, (actual, expected) in enumerate(
        zip(snapshots, fixture["snapshots"])
    ):
        assert actual == expected, f"first mismatch at step {step}"


def test_runs_are_deterministic():
    actions = SCENARIOS["mixed"]
    assert run_scenario(actions) == run_scenario(actions)
