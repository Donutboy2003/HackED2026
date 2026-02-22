"""
Hardware driver for the Waveshare 1.51inch Transparent OLED (128x64).
Based on the working Waveshare OLED_1in51 library + PIL rendering.

Directory layout expected:
  project/
  ├── oled_driver.py       ← this file
  ├── lib/
  │   └── waveshare_OLED/
  │       └── OLED_1in51.py
  └── pic/
      └── Font.ttc
"""

import os
import sys
import math
import logging

from PIL import Image, ImageDraw, ImageFont, ImageOps

# ── Waveshare library path ────────────────────────────────────────────────────
_base_dir = os.path.dirname(os.path.abspath(__file__))
_libdir   = os.path.join(_base_dir, "lib")
if _libdir not in sys.path:
    sys.path.append(_libdir)

from waveshare_OLED import OLED_1in51

from font import ALPHABET
from input_processor import DIR_N, DIR_NE, DIR_E, DIR_SE, DIR_S, DIR_SW, DIR_W, DIR_NW, DIR_CENTER

# logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

# ── Font sizes (px) ───────────────────────────────────────────────────────────
# Display is 128×64 — keep fonts tight.
_FONT_PATH   = os.path.join(_base_dir, "pic", "Font.ttc")
_SIZE_SMALL  = 8    # ~5×7 equivalent — fits 21 chars/row
_SIZE_MEDIUM = 11
_SIZE_LARGE  = 14

# PIL "1" mode convention used by the Waveshare driver:
#   255 = background (pixel off / transparent)
#     0 = foreground (pixel on  / lit)
_BG = 255
_FG = 0


def _load_fonts(path: str) -> dict:
    try:
        return {
            "small":  ImageFont.truetype(path, _SIZE_SMALL),
            "medium": ImageFont.truetype(path, _SIZE_MEDIUM),
            "large":  ImageFont.truetype(path, _SIZE_LARGE),
        }
    except (IOError, OSError) as e:
        log.warning("Could not load TTF font (%s) — falling back to PIL default", e)
        default = ImageFont.load_default()
        return {"small": default, "medium": default, "large": default}


_FONTS = _load_fonts(_FONT_PATH)


# ======================================================================
# OLED Framebuffer — PIL-backed, same public API as before
# ======================================================================

class OLEDBuffer:
    WIDTH  = 128
    HEIGHT = 64

    def __init__(self):
        log.debug("OLEDBuffer init (%d×%d)", self.WIDTH, self.HEIGHT)
        self._image: Image.Image = self._blank_image()
        self._draw:  ImageDraw.ImageDraw = ImageDraw.Draw(self._image)

    # ── Internal helpers ──────────────────────────────────────────────

    def _blank_image(self) -> Image.Image:
        return Image.new("1", (self.WIDTH, self.HEIGHT), _BG)

    def _font(self, size: str = "small") -> ImageFont.FreeTypeFont:
        return _FONTS.get(size, _FONTS["small"])

    def _char_w(self, font) -> int:
        """Approximate fixed character advance width for a font."""
        bbox = font.getbbox("A")
        return (bbox[2] - bbox[0]) + 1

    @property
    def image(self) -> Image.Image:
        """The current PIL Image (read by SSD1309Driver.show)."""
        return self._image

    # ── Primitive drawing (PIL-backed) ────────────────────────────────

    def clear(self):
        self._image = self._blank_image()
        self._draw  = ImageDraw.Draw(self._image)
        log.debug("OLEDBuffer cleared")

    def pixel(self, x: int, y: int, c: int = 1):
        if 0 <= x < self.WIDTH and 0 <= y < self.HEIGHT:
            self._draw.point((x, y), fill=_FG if c else _BG)

    def line(self, x0, y0, x1, y1):
        self._draw.line([(x0, y0), (x1, y1)], fill=_FG)

    def rect(self, x, y, w, h, *, fill=False, outline=True):
        log.debug("rect x=%d y=%d w=%d h=%d fill=%s outline=%s", x, y, w, h, fill, outline)
        x1, y1 = x + w - 1, y + h - 1
        if outline:
            self._draw.rectangle([x, y, x1, y1], outline=_FG, fill=None)
        if fill:
            self._draw.rectangle([x, y, x1, y1], fill=_FG)

    def rect_thick(self, x, y, w, h, thickness):
        log.debug("rect_thick x=%d y=%d w=%d h=%d t=%d", x, y, w, h, thickness)
        for t in range(thickness):
            if w - 2 * t <= 0 or h - 2 * t <= 0:
                break
            self.rect(x + t, y + t, w - 2 * t, h - 2 * t)

    def rect_dwell(self, x, y, w, h, dwell_percent, max_thickness=4):
        thickness = max(1, int(max_thickness * dwell_percent))
        log.debug("rect_dwell dwell=%.2f → thickness=%d", dwell_percent, thickness)
        self.rect_thick(x, y, w, h, thickness)

    def rect_loader(self, x, y, w, h, percent):
        log.debug("rect_loader x=%d y=%d w=%d h=%d pct=%.2f", x, y, w, h, percent)
        if percent <= 0:
            return
        perimeter = []
        for i in range(x, x + w):           perimeter.append((i, y))
        for j in range(y + 1, y + h):       perimeter.append((x + w - 1, j))
        for i in range(x + w - 2, x - 1, -1): perimeter.append((i, y + h - 1))
        for j in range(y + h - 2, y, -1):   perimeter.append((x, j))
        count = max(1, int(len(perimeter) * min(1.0, percent)))
        log.debug("rect_loader: drawing %d / %d perimeter pixels", count, len(perimeter))
        for px, py in perimeter[:count]:
            self.pixel(px, py)

    def string(self, text: str, x: int, y: int, font_size: str = "small"):
        log.debug("string %r at (%d, %d) size=%s", text, x, y, font_size)
        font = self._font(font_size)
        self._draw.text((x, y), text, font=font, fill=_FG)

    def draw_direction_pie(self, direction: str, dwell_percent: float = 0.0):
        """
        Draw a mini 8-wedge direction indicator in the bottom-right corner.
        Active wedge fills with pixels. Dwell shown as shrinking center dot.
        """
        RADIUS = 14
        cx = self.WIDTH  - RADIUS - 2   # 112
        cy = self.HEIGHT - RADIUS - 2   # 48

        _DIR_ANGLES = {
            DIR_N:  90,  DIR_NE: 45,  DIR_E:  0,   DIR_SE: 315,
            DIR_S:  270, DIR_SW: 225, DIR_W:  180,  DIR_NW: 135,
        }

        WEDGE_HALF = 22.5 - 2   # small gap between wedges
        DEAD_R     = 4           # dead zone radius in px

        # Draw all wedge outlines, fill the active one
        for dir_name, center_deg in _DIR_ANGLES.items():
            is_active = direction == dir_name
            a0 = math.radians(center_deg - WEDGE_HALF)
            a1 = math.radians(center_deg + WEDGE_HALF)

            steps = 24
            for step in range(steps + 1):
                a = a0 + (a1 - a0) * step / steps

                # Outer arc edge
                ox = cx + int(RADIUS * math.cos(a))
                oy = cy - int(RADIUS * math.sin(a))
                self.pixel(ox, oy)

                if is_active:
                    # Fill from dead zone edge outward
                    for r in range(DEAD_R, RADIUS):
                        fx = cx + int(r * math.cos(a))
                        fy = cy - int(r * math.sin(a))
                        self.pixel(fx, fy)

            # Wedge boundary spokes
            for a in [a0, a1]:
                for r in range(DEAD_R, RADIUS):
                    sx = cx + int(r * math.cos(a))
                    sy = cy - int(r * math.sin(a))
                    self.pixel(sx, sy)

        # Dead zone circle outline
        steps = 32
        for step in range(steps):
            a = 2 * math.pi * step / steps
            self.pixel(cx + int(DEAD_R * math.cos(a)),
                    cy - int(DEAD_R * math.sin(a)))

        # Dwell indicator — filled center dot that grows with dwell
        if dwell_percent > 0 and direction != DIR_CENTER:
            fill_r = max(1, int(DEAD_R * dwell_percent))
            for dy in range(-fill_r, fill_r + 1):
                for dx in range(-fill_r, fill_r + 1):
                    if dx * dx + dy * dy <= fill_r * fill_r:
                        self.pixel(cx + dx, cy + dy)

    # ── Scene renderers ───────────────────────────────────────────────

    def draw_write_scene(self, *, sentence, prefix, cursor_index, sugg_index,
                         suggestions, dwell_percent, direction):
        log.debug(
            "draw_write_scene cursor=%d sugg=%d prefix=%r dir=%s dwell=%.2f",
            cursor_index, sugg_index, prefix, direction, dwell_percent,
        )

        font  = self._font("small")
        cw    = self._char_w(font)   # ~char advance width in px
        cx    = self.WIDTH  // 2
        cy    = 18

        # ── Status bar ────────────────────────────────────────────────
        full_text = sentence + prefix
        visible   = full_text[-21:]          # fit within 128 px
        self.string(visible, 2, 1)
        cursor_x = 2 + len(visible) * cw
        self.line(cursor_x, 1, cursor_x, 9)  # blinking cursor stub
        self.line(0, 11, self.WIDTH, 11)      # separator
        self.string("W", self.WIDTH - cw - 2, 1)

        # ── Diagonal shortcut overlay ─────────────────────────────────
        _SHORTCUTS = {
            DIR_NE: "$SUGG",
            DIR_SE: "SEND",
            DIR_SW: "DEL WD",
            DIR_NW: "CAPTION",
        }

        if direction in _SHORTCUTS:
            label = _SHORTCUTS[direction].replace(
                "$SUGG", suggestions[0] if suggestions else "…"
            )
            log.debug("draw_write_scene: shortcut overlay %r dir=%s", label, direction)
            lw     = int(font.getlength(label))
            bar_w  = lw + 12
            bar_h  = 13
            bar_x  = cx - bar_w // 2
            bar_y  = 26
            self.rect(bar_x, bar_y, bar_w, bar_h)
            self.rect_loader(bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4, dwell_percent)
            self.string(label, bar_x + 6, bar_y + 3)
            return

        # ── Alphabet row ──────────────────────────────────────────────
        box_w, box_h = cw + 4, 13
        bx = cx - box_w // 2
        by = cy - 2

        if sugg_index == 0:
            self.rect(bx, by, box_w, box_h)
            self.rect_loader(bx - 2, by - 2, box_w + 4, box_h + 4, dwell_percent)

        visible_range = 8
        spacing       = cw + 2
        for offset in range(-visible_range, visible_range + 1):
            ch  = ALPHABET[(cursor_index + offset) % len(ALPHABET)]
            x   = cx + offset * spacing - cw // 2
            if x < -cw or x > self.WIDTH + cw:
                continue
            self.string(ch, x, cy)

        # ── Suggestion list ───────────────────────────────────────────
        list_y  = by + box_h + 3
        line_h  = 10
        max_vis = min(3, len(suggestions))
        log.debug("draw_write_scene: %d suggestions", max_vis)

        for i in range(max_vis):
            word = suggestions[i]
            lw   = int(font.getlength(word))
            sy   = list_y + i * line_h
            sx   = cx - lw // 2
            slot = i + 1

            if sugg_index == slot:
                log.debug("draw_write_scene: suggestion slot %d selected (%r)", slot, word)
                sw = lw + 4
                sh = line_h + 1
                self.rect(sx - 2, sy - 1, sw, sh)
                self.rect_loader(sx - 4, sy - 3, sw + 4, sh + 4, dwell_percent)

            self.string(word, sx, sy)

        self.draw_direction_pie(direction, dwell_percent)

    def draw_caption_scene(self, *, transcript, scroll_offset, paused,
                       direction=DIR_CENTER, dwell_percent=0.0):
        log.debug(
            "draw_caption_scene lines=%d scroll=%d paused=%s",
            len(transcript), scroll_offset, paused,
        )

        font = self._font("small")
        cw   = self._char_w(font)
        cx   = self.WIDTH // 2

        self.string("PAUSED" if paused else "LIVE", 2, 1)
        self.string("C", self.WIDTH - cw - 2, 1)
        self.line(0, 11, self.WIDTH, 11)

        # ── Diagonal shortcut overlays ────────────────────────────────────
        _SHORTCUTS = {
            DIR_NW: "WRITE MODE",
            DIR_NE: "RESTART SENSOR",
            DIR_SE: "RESUME" if paused else "PAUSE",
            DIR_SW: "CLEAR",
        }

        if direction in _SHORTCUTS:
            label = _SHORTCUTS[direction]
            lw    = int(font.getlength(label))
            bar_w = lw + 12
            bar_h = 13
            bar_x = cx - bar_w // 2
            bar_y = 26
            self.rect(bar_x, bar_y, bar_w, bar_h)
            self.rect_loader(bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4, dwell_percent)
            self.string(label, bar_x + 6, bar_y + 3)
            self.draw_direction_pie(direction, dwell_percent)
            return

        # ── Transcript lines ──────────────────────────────────────────────
        max_lines = 5
        line_h    = 10
        start_y   = 13
        total     = len(transcript)
        end_idx   = total - scroll_offset
        start_idx = max(0, end_idx - max_lines)

        for i, line_idx in enumerate(range(start_idx, max(end_idx, start_idx))):
            if line_idx < 0 or line_idx >= total:
                continue
            text = transcript[line_idx]
            log.debug("draw_caption_scene: line %d → %r", line_idx, text)
            self.string(text, 2, start_y + i * line_h)

        if scroll_offset > 0:
            self.string("^", self.WIDTH - cw - 2, start_y)

        self.draw_direction_pie(direction, dwell_percent)



# ======================================================================
# SSD1309 Driver — thin wrapper around OLED_1in51
# ======================================================================

class SSD1309Driver:
    """
    Drives the Waveshare 1.51" Transparent OLED via the official
    Waveshare OLED_1in51 library. All low-level SPI/GPIO is handled
    by that library — this class only manages init, show, and cleanup.
    """

    def __init__(self):
        log.info("SSD1309Driver init via OLED_1in51")
        self._disp = OLED_1in51.OLED_1in51()
        self._disp.Init()
        self._disp.clear()
        log.info("SSD1309Driver ready — %dx%d", self._disp.width, self._disp.height)

    def show(self, oled: OLEDBuffer):
        """Flush an OLEDBuffer to the physical display."""
        log.debug("show: flushing framebuffer")
        flipped = ImageOps.mirror(oled.image)
        buf = self._disp.getbuffer(flipped)
        self._disp.ShowImage(buf)

    def clear(self):
        """Blank the physical display."""
        log.debug("clear: blanking display")
        self._disp.clear()

    def cleanup(self):
        """Release hardware resources."""
        log.info("SSD1309Driver cleanup")
        self._disp.clear()
        self._disp.module_exit()
        log.info("Display shut down")
