"""Regenerates tests/fixtures/behavior/*.json from the current code.

Only run this when a behavior change is intended:
    python -m tests.generate_behavior_fixtures
"""

import json
from pathlib import Path

from tests.harness import config_snapshot, run_legacy, setup_flags
from tests.scenarios import SCENARIOS

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "behavior"


def main() -> None:
    setup_flags()
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for name, actions in SCENARIOS.items():
        fixture = {
            "config": config_snapshot(),
            "actions": [list(action) for action in actions],
            "snapshots": run_legacy(actions),
        }
        path = FIXTURE_DIR / f"{name}.json"
        path.write_text(_dumps(fixture))
        print(f"wrote {path} ({len(actions)} steps)")


def _dumps(fixture: dict) -> str:
    # One line per step, so a diff points at the step that changed.
    lines = [
        "{",
        f' "config": {json.dumps(fixture["config"])},',
        f' "actions": {json.dumps(fixture["actions"])},',
        ' "snapshots": [',
        ",\n".join(f"  {json.dumps(s)}" for s in fixture["snapshots"]),
        " ]",
        "}",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
