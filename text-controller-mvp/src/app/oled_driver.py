"""
Hardware driver for the Waveshare 1.51inch Transparent OLED (128x64).
Controller: SSD1309 via 4-wire SPI on Raspberry Pi 5.

Wiring (default GPIO pins):
  VCC  → 3.3V (Pin 1)
  GND  → GND  (Pin 6)
  DIN  → MOSI (GPIO 10, Pin 19)
  CLK  → SCLK (GPIO 11, Pin 23)
  CS   → CE0  (GPIO  8, Pin 24)
  DC   → GPIO 24 (Pin 35)
  RST  → GPIO 25 (Pin 37)

Install dependencies:
  pip install spidev lgpio
"""

import time
import lgpio
import spidev

from font import FONT_5x7, ALPHABET
from input_processor import (
    DIR_CENTER, DIR_N, DIR_S, DIR_E, DIR_W,
    DIR_NE, DIR_NW, DIR_SE, DIR_SW,
)

# ── GPIO pin numbers (BCM) ────────────────────────────────────────────────────
PIN_DC  = 24
PIN_RST = 25
PIN_CS  = 8

GPIO_CHIP = 4   # RPi5 uses gpiochip4; use 0 for RPi4 and earlier

# ── SPI settings ──────────────────────────────────────────────────────────────
SPI_BUS          = 0
SPI_DEV          = 0
SPI_MAX_SPEED_HZ = 8_000_000

# ── SSD1309 command bytes ─────────────────────────────────────────────────────
_CMD_DISPLAY_OFF      = 0xAE
_CMD_DISPLAY_ON       = 0xAF
_CMD_SET_CONTRAST     = 0x81
_CMD_ENTIRE_ON        = 0xA4
_CMD_NORMAL_DISPLAY   = 0xA6
_CMD_SET_DISP_CLK_DIV = 0xD5
_CMD_SET_MUX_RATIO    = 0xA8
_CMD_SET_DISP_OFFSET  = 0xD3
_CMD_SET_START_LINE   = 0x40
_CMD_MEM_ADDR_MODE    = 0x20
_CMD_SET_SEG_REMAP    = 0xA1
_CMD_COM_SCAN_DEC     = 0xC8
_CMD_SET_COM_PINS     = 0xDA
_CMD_SET_PRECHARGE    = 0xD9
_CMD_SET_VCOM_DESELECT = 0xDB
_CMD_SET_COL_ADDR     = 0x21
_CMD_SET_PAGE_ADDR    = 0x22


# ======================================================================
# OLED Framebuffer
# ======================================================================

class OLEDBuffer:
    WIDTH  = 128
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
        for t in range(thickness):
            if w - 2 * t <= 0 or h - 2 * t <= 0:
                break
            self.rect(x + t, y + t, w - 2 * t, h - 2 * t)

    def rect_dwell(self, x, y, w, h, dwell_percent, max_thickness=4):
        thickness = max(1, int(max_thickness * dwell_percent))
        self.rect_thick(x, y, w, h, thickness)

    def rect_loader(self, x, y, w, h, percent):
        if percent <= 0:
            return
        perimeter = []
        for i in range(x, x + w):
            perimeter.append((i, y))
        for j in range(y + 1, y + h):
            perimeter.append((x + w - 1, j))
        for i in range(x + w - 2, x - 1, -1):
            perimeter.append((i, y + h - 1))
        for j in range(y + h - 2, y, -1):
            perimeter.append((x, j))
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

    def to_ssd1309_bytes(self) -> bytes:
        pages = 8
        data  = bytearray(pages * self.WIDTH)
        for page in range(pages):
            base_row = page * 8
            for col in range(self.WIDTH):
                byte = 0
                for bit in range(8):
                    row = base_row + bit
                    if row < self.HEIGHT and self.buf[row][col]:
                        byte |= (1 << bit)
                data[page * self.WIDTH + col] = byte
        return bytes(data)

    # ── Scene renderers ───────────────────────────────────────────────

    def draw_write_scene(self, *, sentence, prefix, cursor_index, sugg_index,
                         suggestions, dwell_percent, direction):
        cx, cy = 64, 19

        # Status bar
        full_text = sentence + prefix
        visible   = full_text[-20:]
        self.string(visible, 2, 2)
        cursor_x = 2 + len(visible) * 6
        for y in range(2, 10):
            self.pixel(cursor_x, y)
        self.rect(0, 10, 128, 1, fill=True)

        # Mode indicator
        self.string("W", 120, 2)

        # Diagonal shortcut overlay
        _SHORTCUT_LABELS = {
            DIR_NE: "$SUGG",
            DIR_SE: "BACKSPACE",
            DIR_SW: "DEL WORD",
            DIR_NW: "CAPTION",
        }

        if direction in _SHORTCUT_LABELS:
            label = _SHORTCUT_LABELS[direction].replace(
                "$SUGG", suggestions[0] if suggestions else "…"
            )
            label_w = len(label) * 6
            bar_w   = label_w + 12
            bar_h   = 13
            bar_x   = cx - bar_w // 2
            bar_y   = 25
            self.rect(bar_x, bar_y, bar_w, bar_h)
            self.rect_loader(bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4, dwell_percent)
            self.string(label, bar_x + 6, bar_y + 3)
            return

        # Alphabet row
        box_w, box_h = 9, 13
        bx, by = cx - 4, cy - 3

        if sugg_index == 0:
            self.rect(bx, by, box_w, box_h)
            self.rect_loader(bx - 2, by - 2, box_w + 4, box_h + 4, dwell_percent)

        visible_range = 8
        spacing       = 8
        for offset in range(-visible_range, visible_range + 1):
            char_idx = (cursor_index + offset) % len(ALPHABET)
            ch  = ALPHABET[char_idx]
            x   = cx + (offset * spacing) - 2
            y   = cy
            if x < -5 or x > 130:
                continue
            self.char(ch, x, y)

        # Suggestions list
        list_y   = by + box_h + 4
        line_h   = 10
        max_vis  = min(3, len(suggestions))

        for i in range(max_vis):
            word = suggestions[i]
            sy   = list_y + i * line_h
            sx   = cx - (len(word) * 3)
            slot = i + 1
            is_selected = sugg_index == slot

            if is_selected:
                sw = (len(word) * 6) + 3
                sh = 11
                self.rect(sx - 2, sy - 2, sw, sh)
                self.rect_loader(sx - 4, sy - 4, sw + 4, sh + 4, dwell_percent)

            self.string(word, sx, sy)

    def draw_caption_scene(self, *, transcript, scroll_offset, paused):
        self.string("C", 120, 2)

        status = "PAUSED" if paused else "LIVE"
        self.string(status, 2, 2)
        self.rect(0, 10, 128, 1, fill=True)

        max_lines = 5
        line_h    = 10
        start_y   = 13
        total     = len(transcript)
        end_idx   = total - scroll_offset
        start_idx = max(0, end_idx - max_lines)

        for i, line_idx in enumerate(range(start_idx, max(end_idx, start_idx))):
            if line_idx < 0 or line_idx >= total:
                continue
            self.string(transcript[line_idx][:21], 2, start_y + i * line_h)

        if scroll_offset > 0:
            self.string("^", 122, 13)


# ======================================================================
# SSD1309 Hardware Driver
# ======================================================================

class SSD1309Driver:
    def __init__(
        self,
        dc_pin:       int = PIN_DC,
        rst_pin:      int = PIN_RST,
        spi_bus:      int = SPI_BUS,
        spi_dev:      int = SPI_DEV,
        spi_speed_hz: int = SPI_MAX_SPEED_HZ,
        contrast:     int = 0xCF,
        gpio_chip:    int = GPIO_CHIP,
    ):
        self._dc  = dc_pin
        self._rst = rst_pin

        self._h = lgpio.gpiochip_open(gpio_chip)
        lgpio.gpio_claim_output(self._h, self._dc)
        lgpio.gpio_claim_output(self._h, self._rst)

        self._spi = spidev.SpiDev()
        self._spi.open(spi_bus, spi_dev)
        self._spi.max_speed_hz = spi_speed_hz
        self._spi.mode = 0b00

        self._reset()
        self._init_sequence(contrast)

    # ── Low-level helpers ─────────────────────────────────────────────

    def _cmd(self, *commands: int):
        lgpio.gpio_write(self._h, self._dc, 0)
        self._spi.writebytes(list(commands))

    def _data(self, data: bytes):
        lgpio.gpio_write(self._h, self._dc, 1)
        chunk = 4096
        for offset in range(0, len(data), chunk):
            self._spi.writebytes(list(data[offset : offset + chunk]))

    def _reset(self):
        lgpio.gpio_write(self._h, self._rst, 1); time.sleep(0.01)
        lgpio.gpio_write(self._h, self._rst, 0); time.sleep(0.01)
        lgpio.gpio_write(self._h, self._rst, 1); time.sleep(0.01)

    def _init_sequence(self, contrast: int):
        init = [
            (_CMD_DISPLAY_OFF,),
            (_CMD_SET_DISP_CLK_DIV,   0x80),
            (_CMD_SET_MUX_RATIO,      0x3F),
            (_CMD_SET_DISP_OFFSET,    0x00),
            (_CMD_SET_START_LINE | 0x00,),
            (_CMD_MEM_ADDR_MODE,      0x00),   # horizontal addressing
            (_CMD_SET_SEG_REMAP,),
            (_CMD_COM_SCAN_DEC,),
            (_CMD_SET_COM_PINS,       0x12),
            (_CMD_SET_CONTRAST,       contrast),
            (_CMD_SET_PRECHARGE,      0xF1),
            (_CMD_SET_VCOM_DESELECT,  0x40),
            (_CMD_ENTIRE_ON,),
            (_CMD_NORMAL_DISPLAY,),
        ]
        for cmd_tuple in init:
            self._cmd(*cmd_tuple)
        self._cmd(_CMD_DISPLAY_ON)

    # ── Public API ────────────────────────────────────────────────────

    def show(self, oled: OLEDBuffer):
        self._cmd(_CMD_SET_COL_ADDR,  0, OLEDBuffer.WIDTH  - 1)
        self._cmd(_CMD_SET_PAGE_ADDR, 0, OLEDBuffer.HEIGHT // 8 - 1)
        self._data(oled.to_ssd1309_bytes())

    def clear(self):
        self._cmd(_CMD_SET_COL_ADDR,  0, OLEDBuffer.WIDTH  - 1)
        self._cmd(_CMD_SET_PAGE_ADDR, 0, OLEDBuffer.HEIGHT // 8 - 1)
        self._data(bytes(OLEDBuffer.WIDTH * OLEDBuffer.HEIGHT // 8))

    def set_contrast(self, value: int):
        self._cmd(_CMD_SET_CONTRAST, value & 0xFF)

    def display_on(self):  self._cmd(_CMD_DISPLAY_ON)
    def display_off(self): self._cmd(_CMD_DISPLAY_OFF)
    def invert(self, enabled: bool):
        self._cmd(0xA7 if enabled else _CMD_NORMAL_DISPLAY)

    def cleanup(self):
        self.display_off()
        self._spi.close()
        lgpio.gpiochip_close(self._h)
