"""The control center's Agents tab (roadmap step 6c): the roster as cards
or a leaderboard, and the selected agent's profile: skills, skill
history, lineage, and what to do with it.

    ┌ AGENTS  [Cards ▾] [score ▾] ┐ ┌ AGENT ──────────────────────────────┐
    │ ┌ card ──┐ ┌ card ──┐       │ │ name, model, decisions, milestone   │
    │ └────────┘ └────────┘       │ │ ┌ SKILLS ┐ ┌ SKILL HISTORY ▾ ─────┐ │
    │ (or the leaderboard, and    │ │ └────────┘ └──────────────────────┘ │
    │  high scores)               │ │ LINEAGE (a list)                    │
    │                             │ │ [Watch best] [Showcase] ...         │
    └─────────────────────────────┘ └─────────────────────────────────────┘

Its buttons start the Commands tab's actions or open the other tabs, so
nothing here is its own command.
"""

import time
from pathlib import Path
from typing import Callable

import pygame
import pygame_gui
from pygame import Rect
from pygame_gui.elements import UIButton, UIDropDownMenu, UISelectionList

from src.control import agents_data, help, runs
from src.control.agents_data import HISTORY, SKILLS, AgentInfo
from src.control.charts import (
    LEVEL,
    Chart,
    Series,
    compact,
    draw_chart,
    percent,
)
from src.control.jobs import JobManager
from src.control.radar import draw_radar
from src.control.text import PAD, fit, header, wrap
from src.control.tooltips import Tooltips
from src.control.training_plan import busy_agents
from src.render import theme
from src.utils.ui import draw_text

LIST_WIDTH = 600
MARGIN = 16
ROW = 30
GAP = 8
REFRESH = 2.0  # seconds between reads of the agents' files
CARD = (278, 130)
CARD_GAP = (16, 12)
SCROLL_STEP = 40
HISTORY_MENU = 170  # the skill history's picker
VIEWS = ("Cards", "Leaderboard")
SORTS = ("score", "newest", "name", "decisions")
LIT = (20, 60, 95)
CARD_BG = (18, 19, 23)
BADGE_COLORS = {
    "TRAINING": theme.GOOD,
    "MILESTONE": theme.WARN,
    "BRANCHED": theme.ACCENT,
    "FROM YOUR DRIVING": (160, 120, 230),
}
# The leaderboard's columns: (title, width, value).
COLUMNS = (
    ("#", 26, lambda r: "" if r.place is None else str(r.place)),
    ("agent", 150, lambda r: r.name),
    ("score", 70, lambda r: _num(r.metrics.get("score_mean"))),
    ("survive", 62, lambda r: _pct(r.metrics.get("survival"))),
    ("wrecks", 58, lambda r: _pct(r.metrics.get("wreck_rate"))),
    ("cp/min", 56, lambda r: _num(r.metrics.get("checkpoints_per_min"), 1)),
    ("brake", 52, lambda r: _pct(r.metrics.get("braking"))),
    ("best", 90, lambda r: r.checkpoint),
)
BUTTONS_A = (  # (name, width)
    ("Watch best", 110),
    ("Showcase", 100),
    ("Evaluate", 100),
    ("Open run", 100),
)
BUTTONS_B = (("Train more", 110), ("Branch best", 110))


def _num(value, digits: int = 0) -> str:
    return "" if value is None else f"{value:,.{digits}f}"


def _pct(value) -> str:
    return "" if value is None else f"{value:.0%}"


class AgentsTab:
    def __init__(
        self,
        gui,
        area: Rect,
        jobs: JobManager,
        run_action: Callable[[str, dict], object],
        train_more: Callable[[str], None] = lambda agent: None,
        branch: Callable[[str], None] = lambda start: None,
        open_run: Callable[[str], None] = lambda run: None,
        busy: Callable[[], dict] = lambda: {},
        agents_dir: Path | None = None,
        runs_dir: Path | None = None,
        recordings_dir: Path | None = None,
    ) -> None:
        self.gui = gui
        self.jobs = jobs
        self.run_action = run_action
        self.train_more = train_more
        self.branch = branch
        self.open_run = open_run
        self.busy = busy
        self.agents_dir = agents_dir or agents_data.AGENTS_DIR
        self.runs_dir = runs_dir or runs.RUNS_DIR
        self.recordings_dir = recordings_dir
        self.list_box = Rect(area.x, area.y, LIST_WIDTH, area.h)
        self.detail = Rect(
            self.list_box.right + MARGIN,
            area.y,
            area.right - self.list_box.right - MARGIN,
            area.h,
        )
        box = self.list_box
        self.content = Rect(
            box.x + PAD, box.y + 48, box.w - 2 * PAD, box.h - 48 - PAD
        )
        self.view_menu = UIDropDownMenu(
            list(VIEWS),
            VIEWS[0],
            Rect(box.right - PAD - 290, box.y + 8, 140, 26),
            gui,
        )
        self.sort_menu = UIDropDownMenu(
            [f"sort: {s}" for s in SORTS],
            "sort: score",
            Rect(box.right - PAD - 142, box.y + 8, 142, 26),
            gui,
        )
        self.view, self.sort = VIEWS[0], SORTS[0]
        self.scroll = 0
        self.content_height = 0
        self.hit: list[tuple[Rect, str]] = []  # cards or rows: agent id

        d = self.detail
        self.skills_rect = Rect(d.x + PAD, d.y + 116, 250, 236)
        self.history_rect = Rect(
            self.skills_rect.right + 12,
            d.y + 116,
            d.right - PAD - self.skills_rect.right - 12,
            236,
        )
        self.history_menu = UIDropDownMenu(
            [label for label, _ in HISTORY],
            HISTORY[0][0],
            Rect(
                self.history_rect.x + 6,
                self.history_rect.y + 4,
                HISTORY_MENU,
                26,
            ),
            gui,
        )
        self.history_choice = HISTORY[0][0]
        rows_b = d.bottom - PAD - ROW
        rows_a = rows_b - GAP - ROW
        top = self.skills_rect.bottom + 40
        self.phase_list = UISelectionList(
            Rect(d.x + PAD, top, d.w - 2 * PAD, rows_a - 12 - top),
            [],
            gui,
        )
        self.buttons: dict[str, UIButton] = {}
        for row_y, row in ((rows_a, BUTTONS_A), (rows_b, BUTTONS_B)):
            x = d.x + PAD
            for name, width in row:
                self.buttons[name] = UIButton(
                    Rect(x, row_y, width, ROW), name, gui
                )
                x += width + GAP
        self.buttons["Delete agent"] = UIButton(
            Rect(d.right - PAD - 120, rows_b, 120, ROW), "Delete agent", gui
        )
        self.message_x = x + GAP
        self.message_y = rows_b + ROW // 2

        self.agents: list[AgentInfo] = []
        self.base: dict = {}
        self.refs: dict = {}
        self.ranks: list = []
        self.scores: dict = {}
        self._headers: dict = {}  # recording headers read once
        self.selected: str | None = None
        self.phases: list = []
        self._phase_lines: list[str] | None = None
        self.phase: str | None = None  # the picked phase's run
        self.message: tuple[str, tuple] | None = None
        self._refreshed = 0.0
        self.visible = True
        self.tips = Tooltips()  # the window shares its own
        self.refresh(force=True)

    # Showing and hiding with the tab

    def widgets(self) -> list:
        return [
            self.view_menu,
            self.sort_menu,
            self.history_menu,
            self.phase_list,
            *self.buttons.values(),
        ]

    def show(self) -> None:
        self.visible = True
        for widget in self.widgets():
            widget.show()
        if self.view != "Cards":
            self.sort_menu.hide()
        self.refresh(force=True)

    def hide(self) -> None:
        self.visible = False
        for widget in self.widgets():
            widget.hide()

    # Reading the agents

    def refresh(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._refreshed < REFRESH:
            return
        self._refreshed = now
        rows = runs.scan(self.runs_dir, self.jobs.jobs)
        busy = {**busy_agents(rows), **self.busy()}
        self.agents = agents_data.load_agents(self.agents_dir, busy)
        self.base = agents_data.baselines(self.agents_dir)
        self.refs = agents_data.references(self.agents, self.base)
        self.ranks = agents_data.leaderboard(self.agents, self.base)
        self.scores = agents_data.high_scores(
            self.runs_dir, self.recordings_dir, self._headers
        )
        ids = [a.id for a in self.agents]
        if self.selected not in ids:
            self.select(self.ordered()[0].id if ids else None)
        else:
            self._update_phases()
        self._update_buttons()

    def ordered(self) -> list[AgentInfo]:
        return agents_data.sort_agents(self.agents, self.sort)

    @property
    def agent(self) -> AgentInfo | None:
        return next((a for a in self.agents if a.id == self.selected), None)

    def select(self, agent_id: str | None) -> None:
        self.selected = agent_id
        self.message = None
        self.phase = None
        self._phase_lines = None
        self._update_phases()
        self._update_buttons()

    def _update_phases(self) -> None:
        agent = self.agent
        ids = {a.id for a in self.agents}
        self.phases = (
            agents_data.lineage(agent, ids, self.runs_dir) if agent else []
        )
        lines = [f"{i}. {p.text}" for i, p in enumerate(self.phases, 1)]
        if lines != self._phase_lines:
            self._phase_lines = lines
            width = self.phase_list.rect.w - 30
            self.phase_list.set_item_list([fit(t, width) for t in lines])
            if not self.visible:
                self.phase_list.hide()

    def _update_buttons(self) -> None:
        agent = self.agent
        wanted = {
            "Watch best": bool(agent and agent.best),
            "Showcase": bool(agent and agent.best),
            "Evaluate": bool(agent),
            "Open run": bool(self.phase),
            "Train more": bool(agent and not agent.live),
            "Branch best": bool(agent and agent.best_checkpoint),
            "Delete agent": bool(agent and not agent.live),
        }
        for name, on in wanted.items():
            button = self.buttons[name]
            if on and not button.is_enabled:
                button.enable()
            elif not on and button.is_enabled:
                button.disable()

    # Events

    def handle(self, event) -> None:
        if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
            if event.ui_element is self.view_menu:
                self.view = event.text
                self.scroll = 0
                if self.view == "Cards":
                    self.sort_menu.show()
                else:
                    self.sort_menu.hide()
            elif event.ui_element is self.sort_menu:
                self.sort = event.text.replace("sort: ", "")
            elif event.ui_element is self.history_menu:
                self.history_choice = event.text
        elif event.type == pygame_gui.UI_SELECTION_LIST_NEW_SELECTION:
            if event.ui_element is self.phase_list:
                i = self._phase_index(event.text)
                self.phase = self.phases[i].run if i is not None else None
                self._update_buttons()
        elif event.type == pygame_gui.UI_BUTTON_PRESSED:
            for name, button in self.buttons.items():
                if event.ui_element is button:
                    self.press(name)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.click(event.pos)
        elif event.type == pygame.MOUSEWHEEL:
            if self.content.collidepoint(pygame.mouse.get_pos()):
                self.scroll_by(-event.y * SCROLL_STEP)

    def _phase_index(self, text: str) -> int | None:
        width = self.phase_list.rect.w - 30
        lines = [fit(t, width) for t in self._phase_lines]
        return lines.index(text) if text in lines else None

    def click(self, pos) -> None:
        if self.dropdown_open() or not self.content.collidepoint(pos):
            return
        for rect, agent_id in self.hit:
            if rect.collidepoint(pos):
                self.select(agent_id)
                return

    def scroll_by(self, pixels: int) -> None:
        most = max(self.content_height - self.content.h, 0)
        self.scroll = min(max(self.scroll + pixels, 0), most)

    def press(self, name: str) -> None:
        agent = self.agent
        if not agent:
            return
        started = None
        if name == "Watch best":
            started = self.run_action(
                "Watch a driver", {"Driver": f"agent:{agent.id}"}
            )
        elif name == "Showcase":
            started = self.run_action("Showcase", {"Agent": agent.id})
        elif name == "Evaluate":
            started = self.run_action("Evaluate", {"Agent": agent.id})
        elif name == "Open run" and self.phase:
            self.open_run(self.phase)
        elif name == "Train more":
            self.train_more(agent.id)
        elif name == "Branch best" and agent.best_checkpoint:
            self.branch(f"{agent.id}@{agent.best_checkpoint}")
        elif name == "Delete agent":
            self.run_action("Delete an agent", {"Agent": agent.id})
        if started:
            self.message = (f"Started job #{started.number}", theme.GOOD)

    def dropdown_open(self) -> bool:
        return any(
            m.current_state is m.menu_states["expanded"]
            for m in (self.view_menu, self.sort_menu, self.history_menu)
        )

    # Drawing

    def draw(self, surface) -> None:
        for rect in (self.list_box, self.detail):
            pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1)
        header(surface, self.list_box, f"AGENTS · {len(self.agents)}")
        surface.set_clip(self.content)
        self.hit = []
        if not self.agents:
            draw_text(
                surface,
                "No agents yet: create one in the Training tab.",
                (self.content.x, self.content.y),
                theme.TEXT_SIZE,
                theme.TEXT_DIM,
            )
        elif self.view == "Cards":
            self._draw_cards(surface)
        else:
            self._draw_leaderboard(surface)
        surface.set_clip(None)
        self._draw_scrollbar(surface)
        agent = self.agent
        if agent:
            self._draw_profile(surface, agent)
        if self.message:
            text, color = self.message
            room = self.buttons["Delete agent"].rect.x - self.message_x - 8
            draw_text(
                surface,
                fit(text, room),
                (self.message_x, self.message_y),
                theme.TEXT_SIZE,
                color,
                anchor="midleft",
            )

    def _draw_scrollbar(self, surface) -> None:
        view = self.content
        most = self.content_height - view.h
        if most <= 0:
            return
        track = Rect(self.list_box.right - 7, view.y, 3, view.h)
        pygame.draw.rect(surface, theme.BAR_EMPTY, track)
        thumb = max(view.h * view.h // self.content_height, 24)
        y = view.y + (view.h - thumb) * self.scroll // most
        pygame.draw.rect(surface, theme.TEXT_DIM, Rect(track.x, y, 3, thumb))

    def _draw_cards(self, surface) -> None:
        width, height = CARD
        gap_x, gap_y = CARD_GAP
        agents = self.ordered()
        for i, agent in enumerate(agents):
            col, row = i % 2, i // 2
            rect = Rect(
                self.content.x + col * (width + gap_x),
                self.content.y + row * (height + gap_y) - self.scroll,
                width,
                height,
            )
            self._draw_card(surface, rect, agent)
            self.hit.append((rect, agent.id))
        rows = (len(agents) + 1) // 2
        self.content_height = rows * (height + gap_y)

    def _draw_card(self, surface, rect: Rect, agent: AgentInfo) -> None:
        chosen = agent.id == self.selected
        pygame.draw.rect(surface, LIT if chosen else CARD_BG, rect)
        pygame.draw.rect(
            surface, theme.ACCENT if chosen else theme.PANEL_BORDER, rect, 1
        )
        x, y = rect.x + 12, rect.y + 10
        place = agents_data.place_of(agent.id, self.ranks)
        right = rect.right - 12
        if place:
            right = draw_text(
                surface,
                f"#{place}",
                (right, y),
                theme.TEXT_SIZE,
                theme.ACCENT,
                bold=True,
                anchor="topright",
            ).x - 8
        draw_text(
            surface,
            fit(agent.id, right - x, True),
            (x, y),
            theme.TEXT_SIZE,
            theme.TEXT,
            bold=True,
        )
        y += 24
        if agent.score is not None:
            score = draw_text(
                surface,
                f"{agent.score:,.0f}",
                (x, y),
                theme.BIG_SIZE,
                theme.TEXT,
                bold=True,
            )
            ratio = agents_data.heuristic_ratio(agent, self.base)
            if ratio:
                shown = draw_text(
                    surface,
                    f"{ratio:.1f}× heuristic",
                    (score.right + 8, y + 4),
                    theme.HEADER_SIZE,
                    theme.GOOD if ratio >= 1 else theme.TEXT_DIM,
                )
                self.tips.add(shown, help.topic("heuristic ratio"))
        else:
            draw_text(
                surface,
                "not scored yet",
                (x, y + 3),
                theme.TEXT_SIZE,
                theme.TEXT_DIM,
            )
        y += 28
        minutes = agent.seconds / 60
        for line in (
            agent.model,
            f"{_compact(agent.decisions)} · {minutes:,.0f} min",
        ):
            draw_text(
                surface,
                fit(line, rect.w - 100),
                (x, y),
                theme.HEADER_SIZE,
                theme.TEXT_DIM,
            )
            y += 17
        by = rect.bottom - 26
        bx = x
        for badge in agent.badges():
            color = BADGE_COLORS[badge]
            label = draw_text(
                surface, badge, (bx + 6, by + 3), 11, color, bold=True
            )
            pygame.draw.rect(surface, color, label.inflate(12, 6), 1)
            self.tips.add(label.inflate(12, 6), help.topic(f"badge:{badge}"))
            bx = label.right + 14
            if bx > rect.right - 100:
                break
        if agent.best:
            draw_radar(
                surface,
                (rect.right - 44, rect.bottom - 52),
                30,
                agents_data.skills(agent.best, self.refs),
            )

    def _draw_leaderboard(self, surface) -> None:
        x0, y = self.content.x, self.content.y - self.scroll
        x = x0
        for title, width, _ in COLUMNS:
            rect = draw_text(
                surface, title, (x, y), theme.HEADER_SIZE, theme.TEXT_DIM, True
            )
            self.tips.add(rect.inflate(6, 6), help.topic(f"column:{title}"))
            x += width
        y += 24
        for rank in self.ranks:
            baseline = rank.model == "baseline"
            chosen = rank.name == self.selected
            row = Rect(x0 - 6, y - 4, self.content.w + 6, 24)
            if chosen:
                pygame.draw.rect(surface, LIT, row)
            if not baseline:
                self.hit.append((row, rank.name))
            x = x0
            color = theme.TEXT_DIM if baseline else theme.TEXT
            for _, width, value in COLUMNS:
                draw_text(
                    surface,
                    fit(value(rank), width - 8),
                    (x, y),
                    theme.TEXT_SIZE,
                    color,
                )
                x += width
            y += 26
        y += 18
        self.tips.label(
            surface,
            "HIGH SCORES",
            (x0, y),
            help.topic("high scores"),
            theme.HEADER_SIZE,
            theme.ACCENT,
            True,
        )
        y += 20
        for line in wrap(
            "The best single rounds, from runs and your recordings. One "
            "round each: luck of the seed counts, so it's not a ranking.",
            self.content.w,
        ):
            draw_text(surface, line, (x0, y), theme.TEXT_SIZE, theme.TEXT_DIM)
            y += 20
        for key, scores in self.scores.items():
            y += 8
            draw_text(surface, key, (x0, y), theme.TEXT_SIZE, theme.TEXT, True)
            y += 22
            for score in scores:
                draw_text(
                    surface,
                    f"{score.score:,.0f}",
                    (x0 + 60, y),
                    theme.TEXT_SIZE,
                    theme.TEXT,
                    anchor="topright",
                )
                draw_text(
                    surface,
                    fit(f"{score.who} · {score.where}", self.content.w - 80),
                    (x0 + 72, y),
                    theme.TEXT_SIZE,
                    theme.TEXT_DIM,
                )
                y += 20
        self.content_height = y + self.scroll - self.content.y + 8

    def _draw_profile(self, surface, agent: AgentInfo) -> None:
        d = self.detail
        x, width = d.x + PAD, d.w - 2 * PAD
        header(surface, d, "AGENT")
        draw_text(
            surface,
            fit(agent.id, width, True, theme.BIG_SIZE),
            (x, d.y + 34),
            theme.BIG_SIZE,
            theme.TEXT,
            bold=True,
        )
        created = agent.created[:10]
        draw_text(
            surface,
            fit(
                f"{agent.model} · {agent.decisions:,.0f} decisions · "
                f"{agent.seconds / 60:,.0f} min training · created {created}",
                width,
            ),
            (x, d.y + 62),
            theme.TEXT_SIZE,
            theme.TEXT_DIM,
        )
        milestone = agent.milestone
        if milestone:
            text = (
                f"MILESTONE {milestone['name']} at {milestone['checkpoint']} "
                f"(suite {milestone['score_mean']:,.0f}, heuristic "
                f"{milestone['heuristic_score']:,.0f})"
            )
            color = theme.WARN
        elif agent.live:
            text, color = f"TRAINING now: run {agent.live}", theme.GOOD
        else:
            text, color = "No milestone yet", theme.TEXT_DIM
        draw_text(
            surface, fit(text, width), (x, d.y + 84), theme.TEXT_SIZE, color
        )
        self._draw_skills(surface, agent)
        draw_chart(
            surface,
            self.history_rect,
            self._history_chart(agent),
            None if self.dropdown_open() else pygame.mouse.get_pos(),
            title=False,
            reserved=HISTORY_MENU + 22,
        )
        menu = self.history_menu.rect
        mark = self.tips.marker(surface, menu.right + 8, menu.centery)
        self.tips.add(menu.union(mark), help.topic("history"))
        draw_text(
            surface,
            "LINEAGE",
            (x, self.skills_rect.bottom + 16),
            theme.HEADER_SIZE,
            theme.ACCENT,
            bold=True,
        )

    def _draw_skills(self, surface, agent: AgentInfo) -> None:
        rect = self.skills_rect
        pygame.draw.rect(surface, theme.PANEL_BORDER, rect, 1)
        title = "SKILLS"
        if agent.best_checkpoint:
            title += f" · {agent.best_checkpoint}"
        self.tips.label(
            surface,
            title,
            (rect.x + 12, rect.y + 10),
            help.topic("skills"),
            theme.HEADER_SIZE,
            theme.ACCENT,
            bold=True,
        )
        center = (rect.centerx, rect.y + 120)
        if not agent.best:
            draw_text(
                surface,
                "Not scored yet: Evaluate",
                center,
                theme.TEXT_SIZE,
                theme.TEXT_DIM,
                anchor="center",
            )
            return
        heuristic = self.base.get("heuristic")
        drawn = draw_radar(
            surface,
            center,
            60,
            agents_data.skills(agent.best, self.refs),
            reference=(
                agents_data.skills(heuristic, self.refs) if heuristic else None
            ),
            labels=[label for label, _, _ in SKILLS],
        )
        for area, label in drawn:
            self.tips.add(area.inflate(8, 6), help.topic(f"skill:{label}"))
        draw_text(
            surface,
            "outline: heuristic",
            (rect.right - 10, rect.bottom - 8),
            theme.HEADER_SIZE,
            theme.TEXT_DIM,
            anchor="bottomright",
        )

    def _history_chart(self, agent: AgentInfo) -> Chart:
        metric = dict(HISTORY)[self.history_choice]
        rows = agents_data.history(agent)
        points = [(r["decisions"], r[metric]) for r in rows if metric in r]
        # The picker names the metric: the legend shows only its value.
        series = [Series("", points, theme.ACCENT)]
        heuristic = (self.base.get("heuristic") or {}).get(metric)
        if heuristic is not None:
            series.append(
                Series(
                    "heuristic",
                    [(0, heuristic)],
                    theme.TEXT_DIM,
                    LEVEL,
                    priority=1,
                )
            )
        chart = Chart("SKILL HISTORY", series, "{} decisions")
        if metric in ("survival", "wreck_rate", "braking"):
            chart.y_format = chart.value_format = percent
        return chart


def _compact(decisions: float) -> str:
    return f"{compact(decisions)} decisions"
