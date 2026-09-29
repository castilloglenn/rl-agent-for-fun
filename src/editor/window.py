"""The map editor's window (roadmap step 7c1): a game window mode with the
game's layout. The model (model.py) holds the stage; this draws it and
turns the mouse and keys into edits.

    make edit_map STAGE=name

    ┌ TOOLS / SELECTED ┐┌ MAP EDITOR · name · unsaved ┐┌ HELP ┐
    │ STAGE            ││ the field: grid, walls,     ││ keys │
    │                  ││ spawn, checkpoints          ││      │
    └──────────────────┘└─────────────────────────────┘└──────┘
"""

import pygame
from pygame import Rect

from src.control.text import wrap
from src.editor.model import GRID, SPAWN_TURN, EditorModel
from src.render import camera as cameras
from src.render import panels, theme
from src.render.camera import FIT, FOLLOW
from src.render.layout import Layout
from src.sim.geometry import car_corners, direction
from src.sim.stage import StageError
from src.utils.ui import draw_text, get_font

CAR = (24, 16)  # the spawn is drawn as the car
GRID_LINES = 4  # a faint line every 4 grid steps (40 px)
HANDLE = 6  # px: a selected wall's corner squares
PAN_STEP = 40  # px per arrow key
TOOL_KEYS = {
    pygame.K_v: "select",
    pygame.K_w: "wall",
    pygame.K_p: "spawn",
    pygame.K_c: "checkpoint",
}
TOOL_ROWS = (
    ("select", "Select, move", "V"),
    ("wall", "Wall", "W"),
    ("spawn", "Spawn", "P"),
    ("checkpoint", "Checkpoint", "C"),
)
HELP = (
    ("drag", "move"),
    ("drag a corner", "resize a wall"),
    ("Del", "delete"),
    ("Q E / wheel", "turn the spawn"),
    ("M", "checkpoints: random / in order"),
    ("G", "snap to the grid"),
    ("F", "fit / 1:1 (arrows pan)"),
    ("Ctrl+Z  Ctrl+Y", "undo, redo"),
    ("Ctrl+S", "save"),
    ("Esc", "quit"),
)
GRID_COLOR = (20, 21, 26)
MARGIN_COLOR = (38, 40, 48)


class EditorWindow:
    def __init__(self, model: EditorModel) -> None:
        self.model = model
        width, height = model.size
        view_w, view_h = cameras.view_size(width, height)
        self.layout = Layout.for_field(view_w, view_h)
        self.camera = cameras.Camera.for_stage(
            width, height, self.layout.field_view
        )
        self.camera.mode = FIT  # the whole stage first; F for 1:1
        self.pan = [width / 2, height / 2]  # 1:1: the view's center
        self.running = True
        self.confirm_quit = False
        self.message: tuple[str, tuple] | None = None
        # A gesture in progress: ("move", kind, index, dx, dy),
        # ("resize", index, corner), ("wall", x0, y0), or ("pan",).
        self.drag = None
        self.mouse_world = (0.0, 0.0)
        pygame.init()
        pygame.display.set_caption(f"Maze Car · Map editor · {model.name}")
        self.screen = pygame.display.set_mode(self.layout.window.size)
        self.clock = pygame.time.Clock()

    # Input

    def handle(self, event) -> None:
        if event.type == pygame.QUIT:
            self.ask_to_quit()
        elif self.confirm_quit:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.running = False
                elif event.key == pygame.K_ESCAPE:
                    self.confirm_quit = False
        elif event.type == pygame.KEYDOWN:
            self.key(event.key, pygame.key.get_mods())
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.press(event.pos)
            elif event.button == 3 and self.camera.mode == FOLLOW:
                self.drag = ("pan",)
        elif event.type == pygame.MOUSEMOTION:
            self.motion(event.pos, event.rel)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button in (1, 3):
                self.release(event.pos)
        elif event.type == pygame.MOUSEWHEEL:
            if self.model.tool == "spawn" or self.model.selection == (
                "spawn",
                0,
            ):
                self.model.turn_spawn(-event.y * SPAWN_TURN)
                self.model.commit()

    def key(self, key: int, mods: int = 0) -> None:
        model = self.model
        command = mods & (pygame.KMOD_CTRL | pygame.KMOD_META)
        self.message = None
        if command and key == pygame.K_z:
            if mods & pygame.KMOD_SHIFT:
                model.redo()
            else:
                model.undo()
        elif command and key == pygame.K_y:
            model.redo()
        elif command and key == pygame.K_s:
            self.save()
        elif key in TOOL_KEYS:
            model.tool = TOOL_KEYS[key]
        elif key == pygame.K_g:
            model.snapping = not model.snapping
        elif key == pygame.K_f:
            self.camera.mode = FOLLOW if self.camera.mode == FIT else FIT
        elif key == pygame.K_m:
            model.toggle_checkpoint_mode()
            model.commit()
        elif key in (pygame.K_q, pygame.K_e):
            model.turn_spawn(SPAWN_TURN if key == pygame.K_q else -SPAWN_TURN)
            model.commit()
        elif key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            if model.delete():
                model.commit()
        elif key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
            self._pan_by(key)
        elif key == pygame.K_ESCAPE:
            self.ask_to_quit()

    def _pan_by(self, key: int) -> None:
        dx = {pygame.K_LEFT: -1, pygame.K_RIGHT: 1}.get(key, 0)
        dy = {pygame.K_UP: -1, pygame.K_DOWN: 1}.get(key, 0)
        self.pan[0] += dx * PAN_STEP
        self.pan[1] += dy * PAN_STEP

    def ask_to_quit(self) -> None:
        if self.model.dirty:
            self.confirm_quit = True
        else:
            self.running = False

    def save(self) -> None:
        try:
            path = self.model.save()
        except StageError as error:
            self.message = (f"Can't save: {error}", theme.BAD)
            return
        self.message = (f"Saved {path}", theme.GOOD)

    def _world(self, pos) -> tuple[float, float]:
        return self.camera.to_world(*pos)

    def _slack(self) -> float:
        """HANDLE px on screen, in world px."""
        return HANDLE / self.camera.scale

    def press(self, pos) -> None:
        if not self.camera.view.collidepoint(pos):
            return
        model = self.model
        x, y = self._world(pos)
        if model.tool == "wall":
            self.drag = ("wall", x, y)
        elif model.tool == "spawn":
            model.move_spawn(x, y)
            model.selection = ("spawn", 0)
            self.drag = ("move", "spawn", 0, 0.0, 0.0)
        else:
            corner = model.corner_at(x, y, self._slack())
            if corner is not None:
                self.drag = ("resize", model.selection[1], corner)
                return
            found = model.pick(x, y, self._slack() / 2)
            if found is None and model.tool == "checkpoint":
                model.add_checkpoint(x, y)
                model.commit()
                found = model.selection
            model.selection = found
            if found:
                ox, oy = self._anchor(found)
                self.drag = ("move", found[0], found[1], ox - x, oy - y)

    def _anchor(self, found) -> tuple[float, float]:
        """The point that moves with a drag: a wall's top left, the spawn,
        or the checkpoint.
        """
        kind, index = found
        if kind == "wall":
            return tuple(self.model.walls[index][:2])
        if kind == "spawn":
            return self.model.spawn["x"], self.model.spawn["y"]
        return tuple(self.model.points[index])

    def motion(self, pos, rel) -> None:
        self.mouse_world = self._world(pos)
        drag, model = self.drag, self.model
        if not drag:
            return
        x, y = self.mouse_world
        if drag[0] == "pan":
            self.pan[0] -= rel[0]
            self.pan[1] -= rel[1]
        elif drag[0] == "move":
            _, kind, index, dx, dy = drag
            if kind == "wall":
                model.move_wall(index, x + dx, y + dy)
            elif kind == "spawn":
                model.move_spawn(x + dx, y + dy)
            else:
                model.move_checkpoint(index, x + dx, y + dy)
        elif drag[0] == "resize":
            model.resize_wall(drag[1], drag[2], x, y)

    def release(self, pos) -> None:
        drag, self.drag = self.drag, None
        if not drag or drag[0] == "pan":
            return
        if drag[0] == "wall":
            x, y = self._world(pos)
            self.model.add_wall(drag[1], drag[2], x, y)
        self.model.commit()

    # The loop

    def run(self) -> None:
        try:
            while self.running:
                for event in pygame.event.get():
                    self.handle(event)
                self.draw()
                pygame.display.flip()
                self.clock.tick(60)
        except KeyboardInterrupt:  # Stop in the control center, or Ctrl+C
            print("(stopped)", flush=True)
        pygame.quit()

    # Drawing

    def draw(self) -> None:
        self.screen.fill(theme.BACKGROUND)
        cam = self.camera
        if cam.mode == FOLLOW:
            cam.follow(*self.pan)
            self.pan = [
                cam.origin[0] + cam.view.w / 2,
                cam.origin[1] + cam.view.h / 2,
            ]
        self._draw_field()
        self._draw_top_bar()
        self._draw_left()
        self._draw_right()
        if self.confirm_quit:
            self._draw_quit_box()

    def _draw_field(self) -> None:
        cam, model, screen = self.camera, self.model, self.screen
        view = cam.view
        pygame.draw.rect(screen, theme.PANEL_BORDER, view.inflate(2, 2), 1)
        screen.set_clip(view)
        width, height = model.size
        step = GRID * GRID_LINES
        if step * cam.scale >= 8:
            for gx in range(0, int(width) + 1, step):
                start, end = cam.to_screen(gx, 0), cam.to_screen(gx, height)
                pygame.draw.line(screen, GRID_COLOR, start, end)
            for gy in range(0, int(height) + 1, step):
                start, end = cam.to_screen(0, gy), cam.to_screen(width, gy)
                pygame.draw.line(screen, GRID_COLOR, start, end)
        self._box(0, 0, width, height, None, theme.FIELD_BORDER)
        checkpoints = model.checkpoints
        if checkpoints.get("mode") == "random":
            margin = checkpoints.get("border_margin", 40)
            inner = (margin, margin, width - 2 * margin, height - 2 * margin)
            self._box(*inner, None, MARGIN_COLOR)
        for i, wall in enumerate(model.walls):
            chosen = model.selection == ("wall", i)
            outline = theme.ACCENT if chosen else theme.FIELD_BORDER
            rect = self._box(*wall, theme.WALL, outline)
            if chosen:
                corners = (
                    rect.topleft,
                    rect.topright,
                    rect.bottomright,
                    rect.bottomleft,
                )
                for corner in corners:
                    handle = Rect(0, 0, HANDLE + 2, HANDLE + 2)
                    handle.center = corner
                    pygame.draw.rect(screen, theme.ACCENT, handle)
        self._draw_checkpoints()
        self._draw_spawn()
        if self.drag and self.drag[0] == "wall":
            x0, y0 = self.drag[1], self.drag[2]
            x1, y1 = self.mouse_world
            preview = (min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
            self._box(*preview, None, theme.ACCENT)
        screen.set_clip(None)

    def _box(self, x, y, width, height, fill, outline) -> Rect:
        """A stage rectangle on screen (filled and/or outlined)."""
        left, top = self.camera.to_screen(x, y)
        s = self.camera.scale
        rect = Rect(
            round(left),
            round(top),
            max(round(width * s), 1) + 1,
            max(round(height * s), 1) + 1,
        )
        if fill:
            pygame.draw.rect(self.screen, fill, rect)
        if outline:
            pygame.draw.rect(self.screen, outline, rect, 1)
        return rect

    def _draw_checkpoints(self) -> None:
        model, cam = self.model, self.camera
        if model.checkpoints.get("mode") != "scripted":
            return
        radius = model.checkpoints.get("radius", 15)
        spots = [cam.to_screen(x, y) for x, y in model.points]
        if len(spots) > 1:
            pygame.draw.lines(self.screen, theme.GUIDE, True, spots)
        for i, spot in enumerate(spots):
            chosen = model.selection == ("checkpoint", i)
            pygame.draw.circle(
                self.screen,
                theme.ACCENT if chosen else theme.CHECKPOINT,
                spot,
                max(radius * cam.scale, 3),
                width=2,
            )
            draw_text(
                self.screen,
                str(i + 1),
                spot,
                theme.HEADER_SIZE,
                theme.TEXT,
                bold=True,
                anchor="center",
            )

    def _draw_spawn(self) -> None:
        spawn, cam = self.model.spawn, self.camera
        s = cam.scale
        center = cam.to_screen(spawn["x"], spawn["y"])
        corners = car_corners(
            center[0], center[1], spawn["angle"], CAR[0] * s, CAR[1] * s
        )
        pygame.draw.polygon(self.screen, theme.TRAIL_RECENT, corners)
        chosen = self.model.selection == ("spawn", 0)
        pygame.draw.polygon(
            self.screen,
            theme.ACCENT if chosen else theme.HITBOX,
            corners,
            1,
        )
        dx, dy = direction(spawn["angle"])
        tip = (center[0] + dx * 22 * s, center[1] + dy * 22 * s)
        pygame.draw.line(self.screen, theme.HITBOX, center, tip, 2)

    def _draw_top_bar(self) -> None:
        bar = self.layout.top_bar
        pygame.draw.rect(self.screen, theme.PANEL_BORDER, bar, 1)
        y = bar.centery
        x = self._text("MAP EDITOR", bar.x + 14, y, theme.ACCENT, head=True)
        x = self._text(self.model.name, x + 12, y, theme.TEXT, big=True)
        if self.model.dirty:
            x = self._text("unsaved", x + 12, y, theme.WARN)
        else:
            x = self._text("saved", x + 12, y, theme.TEXT_DIM)
        if self.message:
            text, color = self.message
            room = bar.right - 14 - (x + 80)
            draw_text(
                self.screen,
                panels._fit(text, room, theme.TEXT_SIZE),
                (bar.right - 14, y),
                theme.TEXT_SIZE,
                color,
                anchor="midright",
            )

    def _text(self, text, x, y, color, head=False, big=False) -> int:
        """One piece of the top bar's line; returns where it ends."""
        size = theme.TEXT_SIZE
        if head:
            size = theme.HEADER_SIZE
        elif big:
            size = theme.BIG_SIZE
        return draw_text(
            self.screen,
            text,
            (x, y),
            size,
            color,
            bold=head or big,
            anchor="midleft",
        ).right

    def _draw_left(self) -> None:
        model = self.model
        column = panels._Column(self.screen, self.layout.left_panel)
        column.header("TOOLS")
        for tool, label, key in TOOL_ROWS:
            chosen = model.tool == tool
            color = theme.ACCENT if chosen else theme.TEXT
            column.row(label, key, colors=(color, theme.TEXT_DIM))
        column.header("SELECTED")
        for label, value in self._selected_rows():
            column.row(label, value)
        column.header("STAGE")
        width, height = model.size
        column.row("Size", f"{width:g} × {height:g}")
        column.row("Walls", str(len(model.walls)))
        checkpoints = model.checkpoints
        if checkpoints.get("mode") == "scripted":
            column.row("Checkpoints", f"in order, {len(model.points)}")
        else:
            column.row("Checkpoints", "random")
        column.row("Snap", f"{GRID} px" if model.snapping else "off")
        scale = self.camera.scale
        column.row("Camera", "1:1" if scale == 1 else f"fit {scale:.0%}")
        problem = model.problem()
        if problem:
            lines = wrap(f"Can't save: {problem}", 220)
            for line in lines[:3]:
                column.note(line, theme.BAD)
        else:
            column.note("Valid", theme.GOOD)
        column.finish()

    def _selected_rows(self) -> list[tuple[str, str]]:
        model = self.model
        if not model.selection:
            return [("Nothing", "click something")]
        kind, index = model.selection
        if kind == "wall":
            x, y, w, h = model.walls[index]
            return [
                ("Wall", f"{index + 1} of {len(model.walls)}"),
                ("Position", f"{x:g}, {y:g}"),
                ("Size", f"{w:g} × {h:g}"),
            ]
        if kind == "spawn":
            spawn = model.spawn
            return [
                ("Spawn", "the car's start"),
                ("Position", f"{spawn['x']:g}, {spawn['y']:g}"),
                ("Heading", f"{spawn['angle']:g}°"),
            ]
        x, y = model.points[index]
        return [
            ("Checkpoint", f"{index + 1} of {len(model.points)}"),
            ("Position", f"{x:g}, {y:g}"),
        ]

    def _draw_right(self) -> None:
        column = panels._Column(self.screen, self.layout.right_panel)
        column.header("HELP")
        for key, action in HELP:
            column.row(key, action, colors=(theme.TEXT, theme.TEXT_DIM))
        column.finish()

    def _draw_quit_box(self) -> None:
        view = self.layout.field_view
        lines = [
            ("QUIT?", theme.BIG_SIZE, theme.WARN, True),
            ("Unsaved changes will be lost.", theme.TEXT_SIZE, theme.TEXT, 0),
            ("Enter quits · Esc goes back", theme.TEXT_SIZE, theme.TEXT_DIM, 0),
        ]
        width = max(get_font(s, b).size(t)[0] for t, s, _, b in lines)
        box = Rect(0, 0, width + 48, 26 * len(lines) + 24)
        box.center = view.center
        shade = pygame.Surface(box.size, pygame.SRCALPHA)
        shade.fill((*theme.BACKGROUND, 235))
        self.screen.blit(shade, box)
        pygame.draw.rect(self.screen, theme.PANEL_BORDER, box, 1)
        y = box.y + 12 + 13
        for text, size, color, bold in lines:
            draw_text(
                self.screen,
                text,
                (view.centerx, y),
                size,
                color,
                bold=bool(bold),
                anchor="center",
            )
            y += 26


def run_editor(name: str) -> None:
    EditorWindow(EditorModel(name)).run()

