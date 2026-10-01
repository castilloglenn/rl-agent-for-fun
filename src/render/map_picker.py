"""The game window's MAPS box: pick the map to play, with a preview of
the highlighted one. M opens it where a driver drives (watching an agent
or the heuristic) and in the showcase, where each choice is a skill.
The renderer keeps its state and keys; this draws it.
"""

from dataclasses import dataclass

import pygame
from pygame import Rect

from src.render import theme
from src.render.stage_preview import draw_stage_preview
from src.utils.ui import draw_text, get_font

ROW = 24
PAD = 20
LIST_WIDTH = 230
HINT = "Up/Down pick · Enter plays it · Esc closes"


@dataclass(frozen=True)
class MapChoice:
    label: str  # as listed: "pillars", "ruins · yours", "Threading · box"
    stage: dict  # the stage's data, for the preview


def describe(stage: dict) -> str:
    """The preview's caption: "1300 × 700 · scripted, 9 checkpoints"."""
    width, height = stage.get("size", (0, 0))
    checkpoints = stage.get("checkpoints") or {}
    if checkpoints.get("mode") == "scripted":
        count = len(checkpoints.get("points", []))
        kind = f"scripted, {count} checkpoints"
        if checkpoints.get("start") == "seeded":
            kind += ", any start"
    else:
        kind = "random checkpoints"
    walls = len(stage.get("walls", []))
    return f"{width:g} × {height:g} · {walls} walls · {kind}"


def visible(count: int, row: int, rows: int) -> range:
    """The rows shown when there are more than fit: the picked one kept
    in view, near the middle.
    """
    if count <= rows:
        return range(count)
    first = min(max(row - rows // 2, 0), count - rows)
    return range(first, first + rows)


def draw_map_picker(
    surface,
    view: Rect,
    choices: list[MapChoice],
    row: int,
    current: int,
    backdrop,
) -> Rect:
    """The box over the field `view`: the list on the left (the picked
    row lit, the one playing now marked), the picked map's preview and
    caption on the right. `backdrop(rect)` shades the box. Returns it.
    """
    box = Rect(0, 0, min(view.w - 24, 820), min(view.h - 24, 440))
    box.center = view.center
    backdrop(box)
    draw_text(
        surface,
        "MAPS",
        (box.centerx, box.y + 22),
        theme.BIG_SIZE,
        theme.ACCENT,
        bold=True,
        anchor="center",
    )
    top, bottom = box.y + 46, box.bottom - 40
    rows = max((bottom - top) // ROW, 1)
    font = get_font(theme.TEXT_SIZE)
    for line, i in enumerate(visible(len(choices), row, rows)):
        y = top + line * ROW + ROW // 2
        picked = i == row
        if picked:
            lit = Rect(box.x + 8, y - ROW // 2 + 1, LIST_WIDTH, ROW - 2)
            pygame.draw.rect(surface, theme.PANEL_BORDER, lit)
        label = choices[i].label
        if i == current:
            label += "  (now)"
        while font.size(label)[0] > LIST_WIDTH - 16 and len(label) > 1:
            label = label[:-2] + "…"
        draw_text(
            surface,
            label,
            (box.x + PAD, y),
            theme.TEXT_SIZE,
            theme.TEXT if picked else theme.TEXT_DIM,
            bold=picked,
            anchor="midleft",
        )
    if len(choices) > rows:  # more above or below: say so
        draw_text(
            surface,
            f"{row + 1} / {len(choices)}",
            (box.x + 8 + LIST_WIDTH // 2, bottom + 4),
            theme.HEADER_SIZE,
            theme.TEXT_DIM,
            anchor="midtop",
        )
    if choices:
        stage = choices[row].stage
        area = Rect(
            box.x + LIST_WIDTH + 2 * PAD,
            top,
            box.right - PAD - (box.x + LIST_WIDTH + 2 * PAD),
            bottom - top - 28,
        )
        draw_stage_preview(surface, area, stage)
        draw_text(
            surface,
            describe(stage),
            (area.centerx, area.bottom + 14),
            theme.TEXT_SIZE,
            theme.TEXT,
            anchor="center",
        )
    draw_text(
        surface,
        HINT,
        (box.centerx, box.bottom - 18),
        theme.TEXT_SIZE,
        theme.TEXT_DIM,
        anchor="center",
    )
    return box
