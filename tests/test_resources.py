"""Heavy jobs run at a low priority with torch's threads capped (decision
038). Priority can't be raised back, so this runs in child processes, never
in the test process.
"""

import os
import subprocess
import sys

CHECK = (
    "import os, torch\n"
    "from src.utils.resources import share_the_machine\n"
    "print(*share_the_machine())\n"
    "print(*share_the_machine())\n"  # twice: it doesn't stack
    "print(os.getpriority(os.PRIO_PROCESS, 0), torch.get_num_threads())\n"
)


def test_a_heavy_job_runs_at_low_priority_with_cores_free():
    out = subprocess.run(
        [sys.executable, "-c", CHECK],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\n")
    first, second, actual = (line.split() for line in out[:3])
    assert first == second == actual
    niceness, threads = map(int, actual)
    assert niceness >= 10
    assert 1 <= threads <= max((os.cpu_count() or 1) - 2, 1)
