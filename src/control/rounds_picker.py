"""The rounds picker (roadmap 7g2, decision 074): which of a dataset's
rounds an imitation teaches, ticked in a table over the Training tab.

    ☑  when            map            watching          you     score
    ☑  10-04 18:31:02  arena          agent_4@d1100k    5.1 s   2,310
    ☐  10-04 18:25:36  skill_gaps  !  agent_4@d1100k    8.2 s   1,198

- Click a box (or Space) to tick a round; click a row (or Up, Down) to
  see its details on the right.
- "This agent's" shows only rounds correcting this agent's line (and
  plain rounds); "Hide test maps" hides rounds on the suite's maps. Both
  only hide: a hidden ticked round still counts, and the footer says so.
- The footer: what's ticked, your seconds, and warnings (a ticked test
  map). Use (Enter) keeps the ticks; Cancel (Esc) drops them.
"""

import pygame
import pygame_gui
from pygame import Rect
from pygame_gui.elements import UIButton

from src.control.round_picks import RoundFacts, summary
from src.control.text import PAD, fit, header, wrap
from src.render import theme
from src.utils.ui import draw_text

LINE = 26  # a table row
BUTTON = 30
DETAILS = 300  # the right side's width
LIT = (20, 60, 95)  # the row whose details show
BOX = 14  # a tick box's size
# (title, width, value)
COLUMNS = (
    ("when", 128, lambda r: r.when),
    ("map", 150, lambda r: r.stage),
    ("watching", 230, lambda r: r.watched or "(you drove)"),
    ("you", 64, lambda r: f"{r.yours:,.1f} s"),
    ("score", 70, lambda r: f"{r.score:,.0f}"),
)
USE, CANCEL = "use", "cancel"


class RoundsPicker:
    def __init__(
        self,
        gui,
        area: Rect,
        title: str,
        rounds: list[RoundFacts],
        picked: set[str],
        line: set[str],
        extra: str = "",
    ) -> None:
        """`rounds`: the dataset's own rounds, newest first. `picked`:
        ticked now. `line`: this agent's line (whose corrections are
        "this agent's"). `extra`: a footer note (the other players).
        """
        self.gui = gui
        self.area = area
        self.title = title
        self.rounds = rounds
        self.picked = set(picked)
        self.line = line
        self.extra = extra
        self.mine_only = True
        self.hide_tests = True
        self.scroll = 0
        shown = self.shown()
        self.focus = shown[0].name if shown else None
        a = area
        top = a.y + 40
        self.mine_button = UIButton(
            Rect(a.x + PAD, top, 150, BUTTON), "", gui
        )
        self.tests_button = UIButton(
            Rect(a.x + PAD + 158, top, 150, BUTTON), "", gui
        )
        self.all_button = UIButton(
            Rect(a.x + PAD + 330, top, 90, BUTTON), "Tick all", gui
        )
        self.none_button = UIButton(
            Rect(a.x + PAD + 428, top, 90, BUTTON), "Untick all", gui
        )
        bottom = a.bottom - PAD - BUTTON
        self.use_button = UIButton(
            Rect(a.right - PAD - 120, bottom, 120, BUTTON), "Use", gui
        )
        self.cancel_button = UIButton(
            Rect(a.right - PAD - 248, bottom, 120, BUTTON), "Cancel", gui
        )
        self.table = Rect(
            a.x + PAD,
            top + BUTTON + 16,
            a.w - 3 * PAD - DETAILS,
            bottom - 76 - (top + BUTTON + 16),
        )
        self._hit: list[tuple[Rect, Rect, str]] = []  # (row, box, name)
        self._label_buttons()

    # What shows

    def shown(self) -> list[RoundFacts]:
        return [
            r
            for r in self.rounds
            if not (self.hide_tests and r.test_map)
            and not (
                self.mine_only
                and r.correction
                and r.watched_agent not in self.line
            )
        ]

    def _label_buttons(self) -> None:
        """The filters' labels, and a details row that's still shown."""
        shown = [r.name for r in self.shown()]
        if self.focus not in shown:
            self.focus = shown[0] if shown else None
        self.mine_button.set_text(
            "This agent's" if self.mine_only else "Every agent's"
        )
        self.tests_button.set_text(
            "Test maps hidden" if self.hide_tests else "Test maps shown"
        )

    @property
    def hidden_picked(self) -> int:
        shown = {r.name for r in self.shown()}
        return len(self.picked - shown)

    # Events

    def handle(self, event) -> str | None:
        """USE or CANCEL when it's done, else None."""
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            element = event.ui_element
            if element is self.use_button:
                return USE
            if element is self.cancel_button:
                return CANCEL
            if element is self.mine_button:
                self.mine_only = not self.mine_only
            elif element is self.tests_button:
                self.hide_tests = not self.hide_tests
            elif element is self.all_button:
                self.picked |= {r.name for r in self.shown()}
            elif element is self.none_button:
                self.picked -= {r.name for r in self.shown()}
            self._label_buttons()
            self.scroll = min(self.scroll, self.max_scroll)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for row, box, name in self._hit:
                if box.collidepoint(event.pos):
                    self.toggle(name)
                    self.focus = name
                elif row.collidepoint(event.pos):
                    self.focus = name
        elif event.type == pygame.MOUSEWHEEL:
            if self.table.collidepoint(pygame.mouse.get_pos()):
                self.scroll_by(-event.y * LINE * 2)
        elif event.type == pygame.KEYDOWN:
            return self._key(event.key)
        return None

    def _key(self, key: int) -> str | None:
        if key == pygame.K_ESCAPE:
            return CANCEL
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return USE
        shown = [r.name for r in self.shown()]
        if not shown:
            return None
        if key == pygame.K_SPACE and self.focus in shown:
            self.toggle(self.focus)
        elif key in (pygame.K_DOWN, pygame.K_UP):
            at = shown.index(self.focus) if self.focus in shown else -1
            step = 1 if key == pygame.K_DOWN else -1
            self.focus = shown[min(max(at + step, 0), len(shown) - 1)]
            self._scroll_to(shown.index(self.focus))
        return None

    def toggle(self, name: str) -> None:
        self.picked ^= {name}

    @property
    def max_scroll(self) -> int:
        rows = len(self.shown()) * LINE
        return max(rows - (self.table.h - LINE), 0)

    def scroll_by(self, pixels: int) -> None:
        self.scroll = min(max(self.scroll + pixels, 0), self.max_scroll)

    def _scroll_to(self, index: int) -> None:
        top, room = index * LINE, self.table.h - 2 * LINE
        if top < self.scroll:
            self.scroll = top
        elif top > self.scroll + room:
            self.scroll = top - room

    def kill(self) -> None:
        for button in (
            self.mine_button, self.tests_button, self.all_button,
            self.none_button, self.use_button, self.cancel_button,
        ):
            button.kill()

    # Drawing

    def draw(self, surface) -> None:
        """Before the GUI: the box, the table, the details, the footer."""
        a = self.area
        pygame.draw.rect(surface, theme.BACKGROUND, a)
        pygame.draw.rect(surface, theme.ACCENT, a, 1)
        header(surface, a, self.title)
        self._draw_table(surface)
        self._draw_details(surface)
        self._draw_footer(surface)

    def _draw_table(self, surface) -> None:
        table = self.table
        x = table.x + BOX + 12
        for name, width, _ in COLUMNS:
            draw_text(
                surface, name, (x, table.y), theme.HEADER_SIZE,
                theme.TEXT_DIM, True,
            )
            x += width
        body = Rect(table.x - 6, table.y + LINE, table.w + 6, table.h - LINE)
        surface.set_clip(body)
        self._hit = []
        y = body.y - self.scroll
        rows = self.shown()
        for row in rows:
            line = Rect(body.x, y, body.w, LINE)
            if body.colliderect(line):
                if row.name == self.focus:
                    pygame.draw.rect(surface, LIT, line)
                box = Rect(table.x, y + (LINE - BOX) // 2, BOX, BOX)
                self._draw_box(surface, box, row.name in self.picked)
                self._hit.append(
                    (line.clip(body), box.inflate(10, 10), row.name)
                )
                self._draw_row(surface, row, box.right + 12, y + 5)
            y += LINE
        surface.set_clip(None)
        if not rows:
            draw_text(
                surface,
                "No rounds to show: change the filters above."
                if self.rounds
                else "No rounds yet.",
                (table.x, body.y + 4),
                theme.TEXT_SIZE,
                theme.TEXT_DIM,
            )

    def _draw_box(self, surface, box: Rect, ticked: bool) -> None:
        if ticked:
            pygame.draw.rect(surface, theme.ACCENT, box, border_radius=3)
            pygame.draw.lines(  # a tick
                surface, theme.TEXT, False,
                [
                    (box.x + 3, box.centery),
                    (box.x + 6, box.bottom - 4),
                    (box.right - 3, box.y + 3),
                ],
                2,
            )
        else:
            pygame.draw.rect(surface, theme.TEXT_DIM, box, 1, border_radius=3)

    def _draw_row(self, surface, row: RoundFacts, x: int, y: int) -> None:
        for name, width, value in COLUMNS:
            text = fit(value(row), width - 12 - (30 if name == "map" else 0))
            dim = name == "watching" and not row.watched
            color = theme.TEXT_DIM if dim else theme.TEXT
            rect = draw_text(surface, text, (x, y), theme.TEXT_SIZE, color)
            if name == "map" and row.test_map:
                draw_text(  # a test map: taught, it'd measure memory
                    surface, "test", (rect.right + 6, y + 1),
                    theme.HEADER_SIZE, theme.WARN, True,
                )
            x += width

    def _draw_details(self, surface) -> None:
        a = self.area
        box = Rect(
            a.right - PAD - DETAILS, self.table.y, DETAILS, self.table.h
        )
        pygame.draw.rect(surface, theme.PANEL_BORDER, box, 1)
        row = next((r for r in self.rounds if r.name == self.focus), None)
        x, y, width = box.x + 12, box.y + 12, box.w - 24
        if not row:
            draw_text(
                surface, "Click a round to see it here.", (x, y),
                theme.TEXT_SIZE, theme.TEXT_DIM,
            )
            return
        lines = [
            (row.stage, theme.TEXT, True),
            (row.when, theme.TEXT_DIM, False),
            ("", theme.TEXT, False),
        ]
        if row.correction:
            lines += [
                (f"Watching {row.watched}", theme.TEXT, False),
                (
                    f"{row.takeovers} takeovers, {row.yours:,.1f} s of "
                    "your driving",
                    theme.TEXT,
                    False,
                ),
            ]
        else:
            lines.append((f"You drove {row.yours:,.1f} s", theme.TEXT, False))
        lines.append(
            (f"Score {row.score:,.0f}, {row.ended}", theme.TEXT, False)
        )
        if row.correction and row.watched_agent not in self.line:
            lines += [
                ("", theme.TEXT, False),
                (
                    "It corrects another agent, not this one's line.",
                    theme.WARN,
                    False,
                ),
            ]
        if row.test_map:
            lines += [
                ("", theme.TEXT, False),
                (f"{row.test_map}.", theme.WARN, False),
            ]
        lines.append(("", theme.TEXT, False))
        lines.append(
            (
                "Ticked" if row.name in self.picked else "Not ticked",
                theme.GOOD if row.name in self.picked else theme.TEXT_DIM,
                True,
            )
        )
        for text, color, bold in lines:
            for part in wrap(text, width) or [""]:
                draw_text(
                    surface, part, (x, y), theme.TEXT_SIZE, color, bold
                )
                y += 20

    def _draw_footer(self, surface) -> None:
        a = self.area
        y = self.use_button.rect.y - 56
        text = summary(self.rounds, self.picked)
        hidden = self.hidden_picked
        if hidden:
            text += f" ({hidden} ticked but hidden by the filters)"
        if self.extra:
            text += f" · {self.extra}"
        draw_text(
            surface, fit(text, a.w - 2 * PAD), (a.x + PAD, y),
            theme.TEXT_SIZE, theme.TEXT,
        )
        tests = [r for r in self.rounds if r.name in self.picked and r.test_map]
        if tests:
            maps = ", ".join(sorted({r.stage for r in tests}))
            draw_text(
                surface,
                fit(
                    f"Ticked on a test map ({maps}): its skill score would "
                    "measure memory, not skill.",
                    a.w - 2 * PAD,
                ),
                (a.x + PAD, y + 24),
                theme.TEXT_SIZE,
                theme.WARN,
            )
