"""OLED framebuffer + tkinter debug visualization."""

import math
import tkinter as tk
from font import FONT_5x7, ALPHABET
from input_processor import (
    DEADZONE_RADIUS, DEAD_BAND_DEG,
    DIR_CENTER, DIR_N, DIR_S, DIR_E, DIR_W,
    DIR_NE, DIR_NW, DIR_SE, DIR_SW,
    _DIRECTIONS,
)

# Direction labels for debug plot
_DIR_LABELS = {
    DIR_N: (0, -1), DIR_NE: (0.707, -0.707), DIR_E: (1, 0),
    DIR_SE: (0.707, 0.707), DIR_S: (0, 1), DIR_SW: (-0.707, 0.707),
    DIR_W: (-1, 0), DIR_NW: (-0.707, -0.707),
}


# ======================================================================
# OLED Framebuffer
# ======================================================================

class OLEDBuffer:
    WIDTH = 128
    HEIGHT = 64

    def __init__(self):
        self.buf = self._blank()

    def _blank(self):
        return [[0] * self.WIDTH for _ in range(self.HEIGHT)]

    def clear(self):
        self.buf = self._blank()

    def pixel(self, x: int, y: int, c: int = 1):
        if 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT:
            self.buf[y][x] = c

    def rect(self, x, y, w, h, *, fill=False, outline=True):
        if outline:
            for i in range(x, x + w):
                self.pixel(i, y)
                self.pixel(i, y + h - 1)
            for j in range(y, y + h):
                self.pixel(x, j)
                self.pixel(x + w - 1, j)
        if fill:
            for j in range(y, y + h):
                for i in range(x, x + w):
                    self.pixel(i, j)

    def rect_thick(self, x, y, w, h, thickness):
        """Draw a rectangle with a given border thickness (grows inward)."""
        for t in range(thickness):
            if w - 2 * t <= 0 or h - 2 * t <= 0:
                break
            self.rect(x + t, y + t, w - 2 * t, h - 2 * t)

    def rect_dwell(self, x, y, w, h, dwell_percent, max_thickness=4):
        """Draw a rectangle whose border thickens with dwell progress."""
        thickness = max(1, int(max_thickness * dwell_percent))
        self.rect_thick(x, y, w, h, thickness)

    def rect_loader(self, x, y, w, h, percent):
        """Draw a rectangle border that traces clockwise from top-left like a loader."""
        if percent <= 0:
            return

        # Build ordered list of all perimeter pixels (clockwise from top-left)
        perimeter = []

        # Top edge: left to right
        for i in range(x, x + w):
            perimeter.append((i, y))
        # Right edge: top+1 to bottom
        for j in range(y + 1, y + h):
            perimeter.append((x + w - 1, j))
        # Bottom edge: right-1 to left
        for i in range(x + w - 2, x - 1, -1):
            perimeter.append((i, y + h - 1))
        # Left edge: bottom-1 to top+1
        for j in range(y + h - 2, y, -1):
            perimeter.append((x, j))

        # Draw the fraction of the perimeter matching dwell progress
        count = max(1, int(len(perimeter) * min(1.0, percent)))
        for i in range(count):
            px, py = perimeter[i]
            self.pixel(px, py)

    def char(self, ch: str, x: int, y: int, *, invert=False):
        bitmap = FONT_5x7.get(ch, FONT_5x7["?"])
        for col_idx, byte in enumerate(bitmap):
            for row_idx in range(8):
                if (byte >> row_idx) & 1:
                    self.pixel(x + col_idx, y + row_idx, 0 if invert else 1)

    def string(self, text: str, x: int, y: int):
        for ch in text:
            self.char(ch, x, y)
            x += 6

    # --- Write mode scene ---

    def draw_write_scene(self, *, sentence, prefix, cursor_index, sugg_index,
                        suggestions, dwell_percent, direction):
        cx, cy = 64, 19

        # Status bar
        full_text = sentence + prefix
        visible = full_text[-20:]
        self.string(visible, 2, 2)
        cursor_x = 2 + len(visible) * 6
        for y in range(2, 10):
            self.pixel(cursor_x, y)
        self.rect(0, 10, 128, 1, fill=True)

        # Mode indicator
        self.string("W", 120, 2)

        # --- Diagonal shortcut overlay ---
        _SHORTCUT_LABELS = {
            "NE": "$SUGG",
            "SE": "BACKSPACE",
            "SW": "DEL WORD",
            "NW": "CAPTION",
        }

        if direction in _SHORTCUT_LABELS:
            label = _SHORTCUT_LABELS[direction].replace("$SUGG", suggestions[0] if suggestions else "…")
            label_w = len(label) * 6
            bar_w = label_w + 12
            bar_h = 13
            bar_x = cx - bar_w // 2
            bar_y = 25

            self.rect(bar_x, bar_y, bar_w, bar_h)
            self.rect_loader(bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4, dwell_percent)

            text_x = bar_x + 6
            text_y = bar_y + 3
            self.string(label, text_x, text_y)
            return

        # Alphabet row
        box_w, box_h = 9, 13
        bx, by = cx - 4, cy - 3

        if sugg_index == 0:
            self.rect(bx, by, box_w, box_h)
            self.rect_loader(bx - 2, by - 2, box_w + 4, box_h + 4, dwell_percent)

        visible_range = 8
        spacing = 8
        for offset in range(-visible_range, visible_range + 1):
            char_idx = (cursor_index + offset) % len(ALPHABET)
            ch = ALPHABET[char_idx]
            x = cx + (offset * spacing) - 2
            y = cy
            if x < -5 or x > 130:
                continue
            # is_center = offset == 0 and sugg_index == 0
            self.char(ch, x, y)

        # Suggestions
        list_y = by + box_h + 4
        line_h = 10
        max_visible = min(3, len(suggestions))

        for i in range(max_visible):
            word = suggestions[i]
            sy = list_y + i * line_h
            sx = cx - (len(word) * 3)
            slot = i + 1
            is_selected = sugg_index == slot

            if is_selected:
                sw = (len(word) * 6) + 3
                sh = 11
                self.rect(sx - 2, sy - 2, sw, sh)
                self.rect_loader(sx - 4, sy - 4, sw + 4, sh + 4, dwell_percent)

            self.string(word, sx, sy)


    # --- Caption mode scene ---

    def draw_caption_scene(self, *, transcript, scroll_offset, paused):
        self.string("C", 120, 2)

        status = "PAUSED" if paused else "LIVE"
        self.string(status, 2, 2)
        self.rect(0, 10, 128, 1, fill=True)

        max_lines = 5
        line_h = 10
        start_y = 13

        total = len(transcript)
        end_idx = total - scroll_offset
        start_idx = max(0, end_idx - max_lines)

        for i, line_idx in enumerate(range(start_idx, max(end_idx, start_idx))):
            if line_idx < 0 or line_idx >= total:
                continue
            text = transcript[line_idx]
            visible = text[:21]
            self.string(visible, 2, start_y + i * line_h)

        if scroll_offset > 0:
            self.string("^", 122, 13)


# ======================================================================
# OLED → tkinter Canvas
# ======================================================================

class OLEDCanvasRenderer:
    PIXEL_SCALE = 4

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self._grid_drawn = False

    def render(self, oled: OLEDBuffer):
        P = self.PIXEL_SCALE
        self.canvas.delete("pixels")
        for y in range(oled.HEIGHT):
            for x in range(oled.WIDTH):
                if oled.buf[y][x]:
                    self.canvas.create_rectangle(
                        x * P, y * P, (x + 1) * P, (y + 1) * P,
                        fill="white", outline="", tags="pixels",
                    )
        if not self._grid_drawn:
            sw = oled.WIDTH * P
            sh = oled.HEIGHT * P
            for gx in range(0, sw, P):
                self.canvas.create_line(gx, 0, gx, sh, fill="#222", tags="grid")
            for gy in range(0, sh, P):
                self.canvas.create_line(0, gy, sw, gy, fill="#222", tags="grid")
            self._grid_drawn = True


# ======================================================================
# Debug Direction Plot
# ======================================================================

class DirectionPlot:
    """Circular deadzone + 8 wedge debug visualization."""

    SIZE = 300

    def __init__(self, parent: tk.Frame):
        self.center = self.SIZE // 2
        self.canvas = tk.Canvas(parent, width=self.SIZE, height=self.SIZE,
                                bg="#222", highlightthickness=0)
        self.canvas.pack(pady=10)
        self._draw_static()
        self.head_dot = self.canvas.create_oval(0, 0, 0, 0, fill="red")
        self._wedge_items: dict[str, int] = {}

    def _draw_static(self):
        c = self.center
        r_dead = int(DEADZONE_RADIUS * 600)
        edge_r = self.SIZE // 2 - 2

        # Outer circle (plot boundary)
        self.canvas.create_oval(
            c - edge_r, c - edge_r, c + edge_r, c + edge_r,
            fill="#000", outline="#444", width=2, tags="static",
        )

        # Deadzone circle
        self.canvas.create_oval(
            c - r_dead, c - r_dead, c + r_dead, c + r_dead,
            outline="#555", width=1, tags="static",
        )

        # 8 sector boundary lines clipped to outer circle
        for center_deg, _ in _DIRECTIONS:
            for offset in [-22.5, 22.5]:
                angle = math.radians(center_deg + offset)
                x1 = c + int(r_dead * math.cos(angle))
                y1 = c - int(r_dead * math.sin(angle))
                x2 = c + int(edge_r * math.cos(angle))
                y2 = c - int(edge_r * math.sin(angle))
                self.canvas.create_line(x1, y1, x2, y2, fill="#333", tags="static")

        # Dead band shading
        for center_deg, _ in _DIRECTIONS:
            for boundary_offset in [-22.5]:
                bd_angle = center_deg + boundary_offset
                half = DEAD_BAND_DEG
                for dd in range(-int(half), int(half) + 1):
                    a = math.radians(bd_angle + dd)
                    x1 = c + int(r_dead * math.cos(a))
                    y1 = c - int(r_dead * math.sin(a))
                    x2 = c + int(edge_r * math.cos(a))
                    y2 = c - int(edge_r * math.sin(a))
                    self.canvas.create_line(x1, y1, x2, y2, fill="#1a1a1a", tags="static")

        # Direction labels
        label_r = edge_r - 18
        for name, (dx, dy) in _DIR_LABELS.items():
            lx = c + int(dx * label_r)
            ly = c + int(dy * label_r)
            self.canvas.create_text(lx, ly, text=name, fill="#666",
                                    font=("Consolas", 8), tags="static")

    def update(self, roll: float, pitch: float, direction: str,
               dwell_percent: float, flash_direction: str | None, mode: str):
        c = self.center
        scale = 600
        edge_r = self.SIZE // 2 - 2

        # Head dot position (clamp to circle)
        x = c - roll * scale
        y = c - pitch * scale
        dx, dy = x - c, y - c
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > edge_r - 5:
            x = c + dx / dist * (edge_r - 5)
            y = c + dy / dist * (edge_r - 5)
        self.canvas.coords(self.head_dot, x - 5, y - 5, x + 5, y + 5)

        # Dot colour
        if dwell_percent >= 1.0:
            color = "white"
        elif direction in (DIR_NE, DIR_NW, DIR_SE, DIR_SW):
            g = int(255 * dwell_percent)
            color = f"#{255:02x}{255:02x}{g:02x}"
        elif direction != DIR_CENTER:
            color = "#00ff00"
        else:
            color = "red"
        self.canvas.itemconfig(self.head_dot, fill=color)

        # Highlight active wedge (clipped to circle)
        self.canvas.delete("wedge")
        if direction != DIR_CENTER:
            highlight = "#2a4a2a"
            if flash_direction == direction:
                highlight = "#4a8a4a"
            self._draw_wedge(direction, highlight, edge_r)

        # Mode label
        self.canvas.delete("mode")
        self.canvas.create_text(
            self.SIZE - 10, 10, text=mode, fill="#888",
            font=("Consolas", 10, "bold"), anchor="ne", tags="mode",
        )

    def _draw_wedge(self, direction: str, color: str, edge_r: int):
        """Draw a filled wedge clipped to the outer circle."""
        c = self.center
        r_dead = int(DEADZONE_RADIUS * 600)

        center_deg = None
        for deg, d in _DIRECTIONS:
            if d == direction:
                center_deg = deg
                break
        if center_deg is None:
            return

        half_wedge = 22.5 - DEAD_BAND_DEG
        steps = 30

        points = []

        # Inner arc (deadzone edge)
        for i in range(steps + 1):
            a = math.radians(center_deg - half_wedge + (2 * half_wedge * i / steps))
            points.append((c + r_dead * math.cos(a), c - r_dead * math.sin(a)))

        # Outer arc (clipped to circle), reversed
        for i in range(steps, -1, -1):
            a = math.radians(center_deg - half_wedge + (2 * half_wedge * i / steps))
            points.append((c + edge_r * math.cos(a), c - edge_r * math.sin(a)))

        flat = []
        for px, py in points:
            flat.extend([px, py])

        self.canvas.create_polygon(flat, fill=color, outline="", tags="wedge")
