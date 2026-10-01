import json

import pygame
from ml_collections import ConfigDict

from src.drivers.keyboard import KeyboardDriver
from src.drivers.registry import make_driver
from src.envs.maze_car.env import MazeCarEnv
from src.render import theme
from src.render.map_picker import MapChoice
from src.render.panels import LIVE_SHORTCUTS, ModeInfo
from src.replay.recordings import LibraryRecorder, RecordingLibrary
from src.replay.viewer import TRAIL_EVERY
from src.sim.components import Transform
from src.sim.resources import Rng, RoundState, SimClock
from src.sim.rules import load_rules
from src.sim.stage import load_stage
from src.utils import named_files
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
# Watching a driver (not the keyboard): T shows its trail, as in replays.
WATCH_SHORTCUTS = (
    *LIVE_SHORTCUTS[2:-2],
    ("T", "trail: where the car has been"),
    *LIVE_SHORTCUTS[-2:],
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
        stage=None,
        test_drive: str = "",
    ) -> None:
        """round_seconds: above 0, overrides the rules' round length (the
        rules get a new name, so leaderboards don't mix them). autorun:
        start the window loop at once (tests step it with `frame`).
        stage: play this Stage instead of `config.stage`. test_drive: the
        map editor's (7c2) label, for example "saved": never recorded, and
        T or Esc then Enter goes back to the editor.
        """
        self.test_drive = test_drive
        if test_drive:
            record = False
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
        self.config, self.rules, self.reward = config, rules, reward
        self._build_env(stage)
        if test_drive:
            self.env.renderer.mode_keys = {pygame.K_t}  # T: back
            self.env.renderer.quit_words = (
                "BACK TO THE EDITOR?",
                "Enter goes back  ·  Esc keeps driving",
            )
        # You start a round with your first driving key, so the timer
        # doesn't run while you get ready. Other drivers start at once.
        self.wait_for_keys = isinstance(self.driver, KeyboardDriver)
        self.watching = not self.wait_for_keys  # a driver drives: a trail
        # Watching, M picks another map (never while you drive: it would
        # cut a recording short; a test drive stays on its map).
        self.maps: list[str] = []
        if self.watching and not test_drive:
            self.maps = named_files.ordered("stages")
            self._offer_maps(stage.name if stage else config.stage)
        self.trail: list[tuple[float, float]] = []  # where the car has been
        self.paused = False
        self.clock = FixedStepClock(self.env.config.sim.steps_per_second)
        self._new_round()
        if autorun:
            self.run()

    def _build_env(self, stage) -> None:
        self.env = MazeCarEnv(
            self.config,
            driver=self.driver.label,
            random_seeds=True,
            reward=self.reward,
            rules=self.rules,
            recorder=self.recorder,
            stage=stage,
        )

    def _offer_maps(self, playing: str) -> None:
        choices = []
        for name in self.maps:
            path = named_files.find("stages", name)
            label = name
            if not named_files.is_built_in("stages", name):
                label += " · yours"
            choices.append(MapChoice(label, json.loads(path.read_text())))
        current = self.maps.index(playing) if playing in self.maps else -1
        self.env.renderer.offer_maps(choices, current)

    def play_map(self, name: str) -> None:
        """A fresh round on another map, with the same driver."""
        self._build_env(load_stage(name))
        self._offer_maps(name)
        self.paused = False
        self._new_round()

    def _new_round(self) -> None:
        self.world = self.env.world
        self.driver.reset(self._seed())
        self.waiting = self.wait_for_keys
        self.trail = []
        if self.watching:
            self._add_trail_point()

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
        picked = self.env.renderer.take_map_pick()
        if picked is not None:  # the MAPS box (M)
            self.play_map(self.maps[picked])
        if self.env.world is not self.world:  # R started a new game
            self._new_round()
        keys = self.env.renderer.keys_pressed
        if self.test_drive and pygame.K_t in keys:
            self.env.running = False  # back to the editor
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
                self._grow_trail()
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
        if self.test_drive:
            return ModeInfo(
                f"TEST DRIVE · {self.test_drive}",
                theme.ACCENT,
                (("T", "back to the editor"), *LIVE_SHORTCUTS),
                messages,
            )
        if self.watching:
            return ModeInfo(
                "Live play",
                theme.TEXT_DIM,
                WATCH_SHORTCUTS,
                messages,
                trail=self.trail,
            )
        if not self.recorder:
            return ModeInfo(
                "Live play", theme.TEXT_DIM, LIVE_SHORTCUTS, messages
            )
        return ModeInfo("REC", theme.BAD, RECORDING_SHORTCUTS, messages)

    def _grow_trail(self) -> None:
        """A point every TRAIL_EVERY steps while the round runs."""
        if not self.watching or self.env.is_game_over:
            return
        if self.world.resource(SimClock).step % TRAIL_EVERY == 0:
            self._add_trail_point()

    def _add_trail_point(self) -> None:
        transform = self.world.component(self.env.car, Transform)
        self.trail.append((transform.x, transform.y))

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
