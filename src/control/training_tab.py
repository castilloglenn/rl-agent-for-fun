"""The control center's Training tab (roadmap step 6b2): one form for RL,
imitation, or imitation then RL, with the plan it will run, an estimate,
and warnings.

    ┌ TRAINING ───────────────┐ ┌ PLAN ───────────────────────────────┐
    │ Mode, Agent, (Name,     │ │ 1. Create ... 2. Train ...          │
    │ Start, Model), Dataset, │ │ ESTIMATE about 9 min                │
    │ Trainer, Stage, ...     │ │ ! warnings                          │
    │ (the fields scroll)     │ │ IN A TERMINAL: python app.py ... && │
    │                         │ │ [Start]                             │
    └─────────────────────────┘ └─────────────────────────────────────┘

Start runs the plan as a chain of the Commands tab's actions (chains.py),
then the Runs tab follows the new run.
"""

import time
from pathlib import Path
from typing import Callable

import pygame
import pygame_gui
from pygame import Rect
from pygame_gui.elements import UIButton

from src.control import actions, runs
from src.control.actions import REWARD, RULES, SECONDS, STAGE, Field
from src.control.form import Form
from src.control.jobs import JobManager
from src.control.text import PAD, fit, header, wrap
from src.control.training_plan import (
    FRESH,
    MODES,
    NEW_AGENT,
    RL,
    Plan,
    busy_agents,
    make_plan,
    uses_imitation,
    uses_rl,
)
from src.render import theme
from src.utils.ui import draw_text

FORM_WIDTH = 600
MARGIN = 16
ROW = 30
REFRESH = 0.5  # seconds between plan updates
REBUILD = ("Mode", "Agent", "Start")  # fields that change the form
DESCRIPTION = (
    "Train an agent with reinforcement learning, clone your recorded "
    "driving (imitation), or clone it first and then improve it with "
    "reinforcement learning. It runs as a chain of "
    "the Commands tab's actions, and the Runs tab follows it."
)
MAX_STEPS = 6  # plan steps shown


def _starts(also: str = "") -> list[str]:
    """A new agent starts fresh, or branches from any checkpoint (and
    `also`, a start picked elsewhere, if the list doesn't have it).
    """
    found = [FRESH, *actions._checkpoints()[1:]]  # without "(none)"
    return found + ([also] if also and also not in found else [])


def form_fields(
    mode: str, agent: str, start: str, agents_dir: Path | None = None
) -> list[Field]:
    new = agent == NEW_AGENT
    fields = [
        Field("Mode", lambda: list(MODES), RL),
        Field(
            "Agent", lambda: [NEW_AGENT, *_agents(agents_dir)], NEW_AGENT
        ),
    ]
    if new:
        fields += [
            Field("Name", None, "", "a new name, for example rookie2"),
            Field("Start", lambda: _starts(start), FRESH),
        ]
        if start == FRESH:
            fields.append(Field("Model", actions._files("models"), "small"))
    if new or uses_rl(mode):
        fields.append(Field("Seed", None, "0"))
    if uses_imitation(mode):
        fields += [
            Field("Dataset", actions._files("datasets"), "mine"),
            Field(
                "Imitation trainer",
                actions._trainers("imitation"),
                "imitate",
            ),
        ]
    if uses_rl(mode):
        fields += [
            Field("Trainer", actions._trainers("rl"), "default"),
            STAGE,
            RULES,
            SECONDS,
            REWARD,
        ]
    return fields


def _agents(agents_dir: Path | None = None) -> list[str]:
    """The agents, from the folder the control center reads."""
    folder = agents_dir or actions.REPO / "agents"
    return sorted(
        p.name for p in folder.glob("*/") if (p / "model.json").exists()
    )


class TrainingTab:
    def __init__(
        self,
        gui,
        area: Rect,
        jobs: JobManager,
        start_plan: Callable[[Plan], object],
        on_battery: Callable[[], bool] = lambda: False,
        busy: Callable[[], dict] = lambda: {},
        runs_dir: Path | None = None,
        recordings_dir: Path | None = None,
        agents_dir: Path | None = None,
    ) -> None:
        """`start_plan(plan)` runs it (and returns its chain). `busy()`:
        agents a chain here is working on, besides the live runs.
        """
        self.agents_dir = agents_dir
        self.gui = gui
        self.jobs = jobs
        self.start_plan = start_plan
        self.on_battery = on_battery
        self.busy = busy
        self.runs_dir = runs_dir or runs.RUNS_DIR
        self.recordings_dir = recordings_dir
        self.form_box = Rect(area.x, area.y, FORM_WIDTH, area.h)
        self.plan_box = Rect(
            self.form_box.right + MARGIN,
            area.y,
            area.right - self.form_box.right - MARGIN,
            area.h,
        )
        box = self.form_box
        self.description = wrap(DESCRIPTION, box.w - 2 * PAD)
        top = box.y + 40 + 20 * len(self.description) + 16
        self.form = Form(
            gui,
            Rect(
                box.x + PAD, top, box.w - 2 * PAD - 12, box.bottom - PAD - top
            ),
        )
        self.form.build(form_fields(RL, NEW_AGENT, FRESH, agents_dir))
        plan = self.plan_box
        self.start_button = UIButton(
            Rect(plan.x + PAD, plan.bottom - PAD - ROW, 140, ROW),
            "Start",
            gui,
        )
        self.plan: Plan | None = None
        self.message: tuple[str, tuple] | None = None
        self._refreshed = 0.0
        self.visible = True
        self.refresh(force=True)

    # Showing and hiding with the tab

    def show(self) -> None:
        self.visible = True
        self.form.show()
        self.start_button.show()
        self.refresh(force=True)

    def hide(self) -> None:
        self.visible = False
        self.form.hide()
        self.start_button.hide()

    # The plan

    def values(self) -> dict[str, str]:
        return self.form.values()

    def rebuild(self) -> None:
        values = self.values()
        self.form.build(
            form_fields(
                values.get("Mode", RL),
                values.get("Agent", NEW_AGENT),
                values.get("Start", FRESH),
                self.agents_dir,
            ),
            values,
        )
        if not self.visible:
            self.form.hide()
        self.refresh(force=True)

    def train(self, agent: str) -> None:
        """RL for an existing agent, from its newest checkpoint."""
        values = {**self.values(), "Mode": RL, "Agent": agent}
        self.form.build(
            form_fields(RL, agent, FRESH, self.agents_dir), values
        )
        if not self.visible:
            self.form.hide()
        self.message = (
            f"Training {agent} further: check, then Start.",
            theme.ACCENT,
        )
        self.refresh(force=True)

    def branch_from(self, start: str) -> None:
        """RL for a new agent branched from `start` (agent@checkpoint),
        with the name to type.
        """
        values = {**self.values(), "Mode": RL, "Agent": NEW_AGENT}
        values.update(Start=start, Name="")
        self.form.build(
            form_fields(RL, NEW_AGENT, start, self.agents_dir), values
        )
        if not self.visible:
            self.form.hide()
        self.form.widgets["Name"].focus()
        self.message = (f"Branching from {start}: name it.", theme.ACCENT)
        self.refresh(force=True)

    def refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._refreshed < REFRESH:
            return
        self._refreshed = now
        values = self.values()
        rows = runs.scan(self.runs_dir, self.jobs.jobs)
        busy = {**busy_agents(rows), **self.busy()}
        self.plan = make_plan(
            values,
            _agents(self.agents_dir),
            busy,
            runs_dir=self.runs_dir,
            recordings=self._recordings(values),
            on_battery=self.on_battery(),
        )
        button = self.start_button
        if self.plan.blockers and button.is_enabled:
            button.disable()
        elif not self.plan.blockers and not button.is_enabled:
            button.enable()

    def _recordings(self, values: dict) -> int | None:
        """How many recordings the dataset would read (a cheap listing;
        building the dataset itself takes seconds).
        """
        if not uses_imitation(values.get("Mode", RL)):
            return None
        from src.experiments.datasets import (
            DatasetError,
            load_dataset_spec,
            recording_paths,
        )

        try:
            spec = load_dataset_spec(values["Dataset"])
        except (DatasetError, FileNotFoundError, KeyError):
            return None
        return len(recording_paths(spec, self.recordings_dir))

    def start(self) -> None:
        self.refresh(force=True)
        plan = self.plan
        if plan.blockers:
            self.message = (plan.blockers[0], theme.BAD)
            return
        chain = self.start_plan(plan)
        if chain is None:
            self.message = ("It couldn't start: see the console.", theme.BAD)
            return
        n = len(plan.steps)
        self.message = (
            f"Started: {n} step{'s' if n > 1 else ''}.",
            theme.GOOD,
        )

    # Events

    def handle(self, event) -> None:
        if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if self.form.field_of(event.ui_element) in REBUILD:
                self.rebuild()
            else:
                self.refresh(force=True)
        elif event.type == pygame_gui.UI_TEXT_ENTRY_CHANGED:
            self.message = None
        elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            if event.ui_element is self.start_button:
                self.start()
        elif event.type == pygame.MOUSEWHEEL:
            self.form.handle_wheel(event)

    def dropdown_open(self) -> bool:
        return self.form.dropdown_open()

    # Drawing

    def draw(self, surface) -> None:
        """Before the GUI."""
        for rect in (self.form_box, self.plan_box):
            pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1)
        box = self.form_box
        header(surface, box, "TRAINING")
        y = box.y + 40
        for line in self.description:
            draw_text(
                surface,
                line,
                (box.x + PAD, y),
                theme.TEXT_SIZE,
                theme.TEXT_DIM,
            )
            y += 20
        self.form.draw_labels(surface)
        self._draw_plan(surface)
        if self.message:
            text, color = self.message
            button = self.start_button.rect
            draw_text(
                surface,
                fit(text, self.plan_box.right - PAD - button.right - 16),
                (button.right + 16, button.centery),
                theme.TEXT_SIZE,
                color,
                anchor="midleft",
            )

    def draw_after(self, surface) -> None:
        """After the GUI: hints in blank fields."""
        self.form.draw_hints(surface)

    def _draw_plan(self, surface) -> None:
        box, plan = self.plan_box, self.plan
        header(surface, box, "PLAN")
        if not plan:
            return
        x, width = box.x + PAD, box.w - 2 * PAD
        y = box.y + 40
        bottom = self.start_button.rect.y - 16
        for i, step in enumerate(plan.steps[:MAX_STEPS], 1):
            lines = wrap(step.text, width - 24)
            draw_text(surface, f"{i}.", (x, y), theme.TEXT_SIZE, theme.ACCENT)
            for line in lines:
                draw_text(
                    surface, line, (x + 24, y), theme.TEXT_SIZE, theme.TEXT
                )
                y += 20
            y += 6
        y += 8
        y = _section(surface, "ESTIMATE", x, y)
        rect = draw_text(
            surface, plan.estimate, (x, y), theme.BIG_SIZE, theme.TEXT, True
        )
        draw_text(
            surface,
            fit(f"({plan.basis})", x + width - rect.right - 10),
            (rect.right + 10, y + 3),
            theme.TEXT_SIZE,
            theme.TEXT_DIM,
        )
        y += 34
        notes = [(t, theme.BAD) for t in plan.blockers] + [
            (t, theme.WARN) for t in plan.warnings
        ]
        for text, color in notes:
            for line in wrap(f"! {text}", width):
                draw_text(surface, line, (x, y), theme.TEXT_SIZE, color)
                y += 20
            y += 4
        if notes:
            y += 10
        y = _section(surface, "IN A TERMINAL", x, y)
        lines = plan.command_lines()
        for i, command in enumerate(lines):
            text = command + (" &&" if i < len(lines) - 1 else "")
            for line in wrap(text, width, theme.HEADER_SIZE):
                if y + 18 > bottom:
                    return
                draw_text(
                    surface, line, (x, y), theme.HEADER_SIZE, theme.TEXT_DIM
                )
                y += 18


def _section(surface, title: str, x: int, y: int) -> int:
    draw_text(surface, title, (x, y), theme.HEADER_SIZE, theme.ACCENT, True)
    return y + 22
