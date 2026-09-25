class FixedStepClock:
    """Turns real frame times into a whole number of fixed simulation steps.

    Real time only decides how many steps run, never what a step does, so
    the simulation stays deterministic. See
    docs/decisions/008-fixed-timestep-clock.md.
    """

    def __init__(
        self, steps_per_second: int, max_steps_per_frame: int = 8
    ) -> None:
        self.step_seconds = 1 / steps_per_second
        self.max_steps_per_frame = max_steps_per_frame
        self.accumulator = 0.0

    def advance(self, elapsed_seconds: float) -> int:
        """Adds real time. Returns how many steps to simulate now."""
        self.accumulator += elapsed_seconds
        steps = int(self.accumulator / self.step_seconds)
        if steps > self.max_steps_per_frame:
            # After a stall (window drag, breakpoint), skip the backlog
            # instead of freezing while catching up.
            steps = self.max_steps_per_frame
            self.accumulator = 0.0
        else:
            self.accumulator -= steps * self.step_seconds
        return steps

    @property
    def alpha(self) -> float:
        """How far the display is between the last step and the next
        (0 to 1). Used to interpolate drawing.
        """
        return self.accumulator / self.step_seconds
