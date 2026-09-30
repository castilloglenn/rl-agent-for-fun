"""Heavy jobs (training, evaluation, imitation) leave the machine room to
breathe (decision 038, after 141 trainings at once hung it): they run at a
low priority, so the system and the windows always come first, and torch
keeps FREE_CORES cores free. They take longer when the machine is busy,
never the machine's responsiveness.
"""

import os

NICENESS = 10  # 0 is normal priority, 19 the lowest
FREE_CORES = 2
# The heavy commands: app.py's flags that keep the CPU busy for minutes.
HEAVY = (
    "train", "resume", "resume_last", "eval", "eval_baselines", "imitate",
    "run",
)


def is_heavy(argv: list[str]) -> bool:
    """Whether a command line runs a heavy command ("-train ...")."""
    return any(
        arg.startswith("-") and not arg.startswith("--") and arg[1:] in HEAVY
        for arg in argv
    )


def share_the_machine(
    niceness: int = NICENESS, free_cores: int = FREE_CORES
) -> tuple[int, int]:
    """Lowers this process's priority to `niceness` (never raises it back)
    and caps torch's threads. Returns (niceness, torch threads).
    """
    current = os.getpriority(os.PRIO_PROCESS, 0)
    if current < niceness:
        try:
            os.setpriority(os.PRIO_PROCESS, 0, niceness)
            current = niceness
        except OSError:
            pass  # not allowed here: keep going at the current priority
    import torch

    cores = os.cpu_count() or 1
    threads = min(torch.get_num_threads(), max(cores - free_cores, 1))
    torch.set_num_threads(threads)
    return current, threads
