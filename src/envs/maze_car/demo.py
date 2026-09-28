import pygame
from ml_collections import ConfigDict

from src.drivers.keyboard import KeyboardDriver
from src.drivers.registry import make_driver
from src.envs.maze_car.env import MazeCarEnv
from src.render import theme
from src.render.panels import LIVE_SHORTCUTS, ModeInfo
from src.replay.recordings import LibraryRecorder, RecordingLibrary
from src.sim.resources import Rng, RoundState
from src.sim.rules import load_rules
from src.utils.timing import FixedStepClock

RECORDING_SHORTCUTS = (
    ("W A S D / arrows", "drive"),
    ("SPACE", "brake"),
    ("P", "pause / resume"),
    ("R", "restart"),
    ("K", "keep the last round"),
    ("H", "lines"),
    ("F", "camera: follow or fit (big stages)"),
    ("?", "these shortcuts"),
    ("Esc", "quit (asks first)"),
)


class MazeCarDemo:
    """Maze Car in a window, driven live by any driver: the keyboard
    (you) by default, or a baseline such as the heuristic. Your rounds
    are recorded (recordings/<player>/) unless record is False.
    """

    def __init__(
        self,
        config: ConfigDict,
        driver: str = "keyboard",
        player: str = "You",
        reward: str = "default",
        round_seconds: float = 0.0,
        record: bool = True,
        autorun: bool = True,
    ) -> None:
        """round_seconds: above 0, overrides the rules' round length (the
        rules get a new name, so leaderboards don't mix them). autorun:
        start the window loop at once (tests step it with `frame`).
        """
        config = config.copy_and_resolve_references()
        config.show_gui = True  # the demo is always drawn
        self.driver = make_driver(driver, player=player)
        rules = load_rules(config.rules)
        if round_seconds > 0:
            rules = rules.with_round_seconds(round_seconds)
        self.recorder = None
        if record and isinstance(self.driver, KeyboardDriver):
            self.recorder = LibraryRecorder(
                {"1": self.driver.record()}, RecordingLibrary(player)
            )
        self.env = MazeCarEnv(
            config,
            driver=self.driver.label,
            random_seeds=True,
            reward=reward,
            rules=rules,
            recorder=self.recorder,
        )
        # You start a round with your first driving key, so the timer
        # doesn't run while you get ready. Other drivers start at once.
        self.wait_for_keys = isinstance(self.driver, KeyboardDriver)
        self.paused = False
        self.clock = FixedStepClock(self.env.config.sim.steps_per_second)
        self._new_round()
        if autorun:
            self.run()

    def _new_round(self) -> None:
        self.world = self.env.world
        self.driver.reset(self._seed())
        self.waiting = self.wait_for_keys

    def run(self) -> None:
        """Fixed-rate simulation steps, drawn at the display's rate."""
        elapsed = self.env.render(mode=self.mode())
        try:
            while self.env.running:
                elapsed = self.frame(elapsed)
        except KeyboardInterrupt:  # Stop in the control center, or Ctrl+C
            print("(stopped)", flush=True)
        self.env.finish_recording()  # a round cut short by quitting

    def frame(self, elapsed: float) -> float:
        """One frame: steps for `elapsed` real seconds (unless paused, a
        box is open, or the round waits for your first key), then draws.
        Returns the real seconds this frame took.
        """
        if self.env.world is not self.world:  # R started a new game
            self._new_round()
        keys = self.env.renderer.keys_pressed
        if self.recorder and pygame.K_k in keys:
            self.recorder.keep_last()
        if pygame.K_p in keys:
            self.paused = not self.paused
        # Pump first so the key state is current for this frame.
        # Pumping leaves the events queued for the renderer.
        pygame.event.pump()
        frozen = self.paused or self.env.renderer.modal_open
        if self.waiting and not frozen:
            action = self.driver.act(self.env.last_observation)
            if any(action):
                self.waiting = False  # the timer starts now
                self.driver.reset(self._seed())
        if frozen or self.waiting:
            self.clock.advance(0)
        else:
            for _ in range(self.clock.advance(elapsed)):
                action = self.driver.act(self.env.last_observation)
                self.env.step_world(action)
        alpha = 1.0 if frozen or self.waiting else self.clock.alpha
        return self.env.render(alpha, self.mode())

    def mode(self) -> ModeInfo:
        """The recording indicator, the waiting and paused prompts, and
        what happened to the last round.
        """
        if self.paused:
            messages = (
                ("PAUSED", theme.WARN),
                ("P resumes", theme.TEXT_DIM),
            )
        elif self.waiting:
            messages = (("Press a driving key to start", theme.ACCENT),)
        else:
            messages = self._saved_messages()
        if not self.recorder:
            return ModeInfo(
                "Live play", theme.TEXT_DIM, LIVE_SHORTCUTS, messages
            )
        return ModeInfo("REC", theme.BAD, RECORDING_SHORTCUTS, messages)

    def _saved_messages(self) -> tuple:
        if not self.recorder:
            return ()
        messages = ()
        saved = self.recorder.last_saved
        if saved and self.env.world.resource(RoundState).over:
            if self.recorder.last_kept:
                messages = (
                    (f"Kept: {saved.parent.name}/{saved.name}", theme.GOOD),
                )
            else:
                messages = (
                    (f"Saved: {saved.name}", theme.TEXT_DIM),
                    ("Press K to keep it", theme.ACCENT),
                )
        return messages

    def _seed(self) -> int:
        return self.env.world.resource(Rng).seed
