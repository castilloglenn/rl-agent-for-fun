"""Colors and sizes shared by the simulation window."""

from src.utils.types import ColorValue

BACKGROUND: ColorValue = (10, 10, 12)
PANEL_BORDER: ColorValue = (44, 46, 54)
FIELD_BORDER: ColorValue = PANEL_BORDER  # gray, like the panels (was white)
WALL: ColorValue = (28, 29, 35)  # a wall's fill, outlined like the border

TEXT: ColorValue = (235, 235, 240)
TEXT_DIM: ColorValue = (130, 133, 145)
ACCENT: ColorValue = (0, 134, 212)  # section headers, pressed keys
GOOD: ColorValue = (70, 200, 120)
WARN: ColorValue = (240, 180, 60)  # caution
BAD: ColorValue = (230, 80, 80)  # danger

RAY: ColorValue = (70, 72, 82)  # muted; warning rays use WARN / BAD
CHECKPOINT: ColorValue = (70, 200, 120)
GUIDE: ColorValue = (40, 95, 65)  # faint line from car to checkpoint
# The agent's sense of the route (7f7): its remembered waypoint, and the
# whole route faint (the agent sees only the waypoint).
ROUTE: ColorValue = (175, 125, 245)
ROUTE_FAINT: ColorValue = (75, 65, 110)
HITBOX: ColorValue = (255, 255, 255)
HIT: ColorValue = (230, 80, 80)  # a car blinks this after a hit
TRAIL_RECENT: ColorValue = (90, 190, 255)  # the car's last seconds
TRAIL_OLD: ColorValue = (78, 81, 92)  # muted gray, still noticeable
WRECKED: ColorValue = (110, 32, 32)  # a wrecked car
BAR_EMPTY: ColorValue = (44, 46, 54)  # unfilled blocks of a bar

# Helvetica Neue: crisp at small sizes, and its digits all have the same
# width, so changing numbers don't wobble. "monospace" (Courier) before.
FONT_FAMILY = "helveticaneue"

HEADER_SIZE = 13
TEXT_SIZE = 14
BIG_SIZE = 18
LINE_HEIGHT = 20
