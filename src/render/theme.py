"""Colors and sizes shared by the simulation window."""

from src.utils.types import ColorValue

BACKGROUND: ColorValue = (10, 10, 12)
PANEL_BORDER: ColorValue = (44, 46, 54)
FIELD_BORDER: ColorValue = (255, 255, 255)

TEXT: ColorValue = (235, 235, 240)
TEXT_DIM: ColorValue = (130, 133, 145)
ACCENT: ColorValue = (0, 134, 212)  # section headers, pressed keys
GOOD: ColorValue = (70, 200, 120)
WARN: ColorValue = (240, 180, 60)  # caution
BAD: ColorValue = (230, 80, 80)  # danger

RAY: ColorValue = (70, 72, 82)  # muted; warning rays use WARN / BAD
CHECKPOINT: ColorValue = (70, 200, 120)
GUIDE: ColorValue = (40, 95, 65)  # faint line from car to checkpoint
HITBOX: ColorValue = (255, 255, 255)

HEADER_SIZE = 13
TEXT_SIZE = 14
BIG_SIZE = 18
LINE_HEIGHT = 20
