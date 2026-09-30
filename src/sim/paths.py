"""How far a point is from a goal along a drivable path around the walls
(roadmap 7e, decision 041). The agent's progress reward uses it; the agent
never sees it.

With no walls, the field is a rectangle, so the shortest path is the
straight line. With walls: a grid over the field (CELL px), the walls and
the border grown by CLEARANCE (half the car's width, so a gap narrower than
the car is closed), and every open cell's path length to the goal
(Dijkstra over 8 neighbors, no cutting corners). A point's distance blends
its 4 surrounding cells (bilinear, so it never jumps as the car crosses
from cell to cell); next to a wall, where one of them is closed, it's the
best of the open ones plus the straight line to it. Deterministic, so
replays verify.
"""

import heapq
import math

CELL = 10.0  # px
CLEARANCE = 8.0  # px: half the car's width
RING = 3  # cells searched around a point (or the goal) for an open one
DIAGONAL = math.sqrt(2.0)
INF = math.inf


class PathField:
    """Path distances to one goal on one stage."""

    def __init__(self, rect, boxes, goal, cell=CELL, clearance=CLEARANCE):
        """rect: the field (x, y, width, height). boxes: the walls
        (left, top, right, bottom). goal: (x, y).
        """
        self.goal = goal
        self.open_field = not boxes
        if self.open_field:
            return
        x, y, width, height = rect
        self.x0, self.y0, self.cell = x, y, cell
        self.cols = max(math.ceil(width / cell), 1)
        self.rows = max(math.ceil(height / cell), 1)
        self.open = self._open_cells(rect, boxes, clearance)
        self.dist = self._distances()

    def _center(self, i: int, j: int) -> tuple[float, float]:
        return (
            self.x0 + (i + 0.5) * self.cell,
            self.y0 + (j + 0.5) * self.cell,
        )

    def _open_cells(self, rect, boxes, clearance) -> list[bool]:
        x, y, width, height = rect
        cols, rows, cell = self.cols, self.rows, self.cell
        is_open = [True] * (cols * rows)

        def span(low: float, high: float, origin: float, count: int):
            """Cells whose centers lie strictly between low and high."""
            first = max(math.floor((low - origin) / cell - 0.5) + 1, 0)
            last = min(math.ceil((high - origin) / cell - 0.5) - 1, count - 1)
            return range(first, last + 1)

        for i in range(cols):  # the border, grown
            cx = self._center(i, 0)[0]
            if cx < x + clearance or cx > x + width - clearance:
                for j in range(rows):
                    is_open[j * cols + i] = False
        for j in range(rows):
            cy = self._center(0, j)[1]
            if cy < y + clearance or cy > y + height - clearance:
                for i in range(cols):
                    is_open[j * cols + i] = False
        for left, top, right, bottom in boxes:  # the walls, grown
            columns = span(left - clearance, right + clearance, x, cols)
            for j in span(top - clearance, bottom + clearance, y, rows):
                for i in columns:
                    is_open[j * cols + i] = False
        return is_open

    def _distances(self) -> list[float]:
        cols, rows, cell = self.cols, self.rows, self.cell
        dist = [INF] * (cols * rows)
        heap = []
        gx, gy = self.goal
        for index in self._open_near(gx, gy):
            cx, cy = self._center(index % cols, index // cols)
            dist[index] = math.hypot(cx - gx, cy - gy)
            heap.append((dist[index], index))
        heapq.heapify(heap)
        is_open = self.open
        straight = ((1, 0), (-1, 0), (0, 1), (0, -1))
        corners = ((1, 1), (1, -1), (-1, 1), (-1, -1))
        diagonal = cell * DIAGONAL
        while heap:
            d, index = heapq.heappop(heap)
            if d > dist[index]:
                continue
            i, j = index % cols, index // cols
            for di, dj in straight:
                a, b = i + di, j + dj
                if 0 <= a < cols and 0 <= b < rows:
                    n = b * cols + a
                    if is_open[n] and d + cell < dist[n]:
                        dist[n] = d + cell
                        heapq.heappush(heap, (d + cell, n))
            for di, dj in corners:
                a, b = i + di, j + dj
                if not (0 <= a < cols and 0 <= b < rows):
                    continue
                n = b * cols + a
                side_1, side_2 = j * cols + a, b * cols + i
                if (
                    is_open[n]
                    and is_open[side_1]
                    and is_open[side_2]
                    and d + diagonal < dist[n]
                ):
                    dist[n] = d + diagonal
                    heapq.heappush(heap, (d + diagonal, n))
        return dist

    def _open_near(self, x: float, y: float) -> list[int]:
        """The open cells around a point: its nearest 2x2, or the nearest
        ring (up to RING cells out) that has any.
        """
        cols, rows = self.cols, self.rows
        fi = (x - self.x0) / self.cell - 0.5
        fj = (y - self.y0) / self.cell - 0.5
        i0, j0 = math.floor(fi), math.floor(fj)
        for reach in range(RING + 1):
            found = []
            for j in range(j0 - reach, j0 + 2 + reach):
                for i in range(i0 - reach, i0 + 2 + reach):
                    if 0 <= i < cols and 0 <= j < rows:
                        index = j * cols + i
                        if self.open[index]:
                            found.append(index)
            if found:
                return found
        return []

    def distance(self, x: float, y: float) -> float:
        """The path length from (x, y) to the goal (inf if no open cell is
        near, for example deep inside a wall).
        """
        gx, gy = self.goal
        if self.open_field:
            return math.hypot(x - gx, y - gy)
        fi = (x - self.x0) / self.cell - 0.5
        fj = (y - self.y0) / self.cell - 0.5
        i0, j0 = math.floor(fi), math.floor(fj)
        if 0 <= i0 < self.cols - 1 and 0 <= j0 < self.rows - 1:
            at = j0 * self.cols + i0
            corners = (at, at + 1, at + self.cols, at + self.cols + 1)
            values = [self.dist[c] for c in corners]
            if not any(math.isinf(v) for v in values):
                u, v = fi - i0, fj - j0
                top = values[0] * (1 - u) + values[1] * u
                bottom = values[2] * (1 - u) + values[3] * u
                return top * (1 - v) + bottom * v
        best = INF
        for index in self._open_near(x, y):
            cx, cy = self._center(index % self.cols, index // self.cols)
            best = min(best, self.dist[index] + math.hypot(x - cx, y - cy))
        return best
