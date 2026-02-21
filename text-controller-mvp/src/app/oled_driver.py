"""
Hardware driver for the Waveshare 1.51inch Transparent OLED (128x64).
Controller: SSD1309 via 4-wire SPI on Raspberry Pi.

Wiring (default GPIO pins):
  VCC  → 3.3V (Pin 1)
  GND  → GND  (Pin 6)
  DIN  → MOSI (GPIO 10, Pin 19)
  CLK  → SCLK (GPIO 11, Pin 23)
  CS   → CE0  (GPIO  8, Pin 24)
  DC   → GPIO 24 (Pin 35)
  RST  → GPIO 25 (Pin 37)

Install dependencies:
  pip install spidev RPi.GPIO
"""

import time
import spidev
import RPi.GPIO as GPIO


# ── GPIO pin numbers (BCM) ────────────────────────────────────────────────────
PIN_DC = 24   # Data / Command select
PIN_RST = 25   # Reset (active-low)
# Chip-select (CE0) — also driven by spidev, kept here for clarity
PIN_CS = 8

# ── SPI settings ──────────────────────────────────────────────────────────────
SPI_BUS = 0
SPI_DEV = 0
SPI_MAX_SPEED_HZ = 8_000_000   # 8 MHz; SSD1309 supports up to ~10 MHz


# ======================================================================
# SSD1309 command bytes
# ======================================================================
_CMD_DISPLAY_OFF = 0xAE
_CMD_DISPLAY_ON = 0xAF
_CMD_SET_CONTRAST = 0x81
_CMD_ENTIRE_ON = 0xA4   # follow RAM content
_CMD_NORMAL_DISPLAY = 0xA6
_CMD_SET_DISP_CLK_DIV = 0xD5
_CMD_SET_MUX_RATIO = 0xA8
_CMD_SET_DISP_OFFSET = 0xD3
_CMD_SET_START_LINE = 0x40
_CMD_CHARGE_PUMP = 0x8D   # NOTE: SSD1309 has an external VCC path;
# keep for compatibility — may be a no-op
_CMD_MEM_ADDR_MODE = 0x20
_CMD_SET_SEG_REMAP = 0xA1   # column 127 → SEG0  (flip horizontal)
_CMD_COM_SCAN_DEC = 0xC8   # scan from COM[N-1] to COM0 (flip vertical)
_CMD_SET_COM_PINS = 0xDA
_CMD_SET_PRECHARGE = 0xD9
_CMD_SET_VCOM_DESELECT = 0xDB
_CMD_SET_COL_ADDR = 0x21
_CMD_SET_PAGE_ADDR = 0x22


# ======================================================================
# OLED Framebuffer  (identical API to the tkinter version)
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
        from font import FONT_5x7
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
        """
        Convert the pixel buffer to SSD1309 page-addressed byte format.

        Layout: 8 pages × 128 columns.
        Each byte covers 8 vertical pixels; bit-0 = topmost row of that page.
        """
        pages = 8           # 64 rows / 8 bits per byte
        data = bytearray(pages * self.WIDTH)
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


# ======================================================================
# SSD1309 Hardware Driver
# ======================================================================

class SSD1309Driver:
    """
    Drives the Waveshare 1.51" Transparent OLED (SSD1309) over 4-wire SPI.

    Usage:
        driver = SSD1309Driver()
        oled   = OLEDBuffer()
        # … draw into oled …
        driver.show(oled)
        # … when done …
        driver.cleanup()
    """

    def __init__(
        self,
        dc_pin:  int = PIN_DC,
        rst_pin: int = PIN_RST,
        spi_bus: int = SPI_BUS,
        spi_dev: int = SPI_DEV,
        spi_speed_hz: int = SPI_MAX_SPEED_HZ,
        contrast: int = 0xCF,
    ):
        self._dc = dc_pin
        self._rst = rst_pin

        # ── GPIO setup ────────────────────────────────────────────────
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self._dc,  GPIO.OUT)
        GPIO.setup(self._rst, GPIO.OUT)

        # ── SPI setup ─────────────────────────────────────────────────
        self._spi = spidev.SpiDev()
        self._spi.open(spi_bus, spi_dev)
        self._spi.max_speed_hz = spi_speed_hz
        self._spi.mode = 0b00          # CPOL=0, CPHA=0

        # ── Initialise the controller ─────────────────────────────────
        self._reset()
        self._init_sequence(contrast)

    # ── Low-level SPI helpers ──────────────────────────────────────────

    def _cmd(self, *commands: int):
        """Send one or more command bytes."""
        GPIO.output(self._dc, GPIO.LOW)
        self._spi.writebytes(list(commands))

    def _data(self, data: bytes):
        """Send raw data bytes (pixel payload)."""
        GPIO.output(self._dc, GPIO.HIGH)
        # spidev has a 4096-byte transfer limit by default; chunk if needed
        chunk = 4096
        for offset in range(0, len(data), chunk):
            self._spi.writebytes(list(data[offset: offset + chunk]))

    def _reset(self):
        """Hardware reset pulse."""
        GPIO.output(self._rst, GPIO.HIGH)
        time.sleep(0.01)
        GPIO.output(self._rst, GPIO.LOW)
        time.sleep(0.01)
        GPIO.output(self._rst, GPIO.HIGH)
        time.sleep(0.01)

    # ── Initialisation sequence ────────────────────────────────────────

    def _init_sequence(self, contrast: int):
        """SSD1309 power-on initialisation (matches Waveshare reference demo)."""
        init = [
            # Display off during init
            (_CMD_DISPLAY_OFF,),
            # Clock: divide ratio=1, oscillator freq=8
            (_CMD_SET_DISP_CLK_DIV, 0x80),
            # Multiplex ratio = 63 (1/64 duty)
            (_CMD_SET_MUX_RATIO, 0x3F),
            # Display offset = 0
            (_CMD_SET_DISP_OFFSET, 0x00),
            # Start line = 0
            (_CMD_SET_START_LINE | 0x00,),
            # Horizontal memory addressing mode
            (_CMD_MEM_ADDR_MODE, 0x00),
            # Segment remap: col 127 → SEG0
            (_CMD_SET_SEG_REMAP,),
            # COM scan direction: descending
            (_CMD_COM_SCAN_DEC,),
            # COM pin config: alternative, no remap
            (_CMD_SET_COM_PINS, 0x12),
            # Contrast
            (_CMD_SET_CONTRAST, contrast),
            # Pre-charge period: phase1=1, phase2=15
            (_CMD_SET_PRECHARGE, 0xF1),
            # VCOM deselect level = 0.83 × VCC
            (_CMD_SET_VCOM_DESELECT, 0x40),
            # Follow RAM content (not entire display on)
            (_CMD_ENTIRE_ON,),
            # Normal (non-inverted) display
            (_CMD_NORMAL_DISPLAY,),
        ]
        for cmd_tuple in init:
            self._cmd(*cmd_tuple)

        self.set_contrast(contrast)
        self._cmd(_CMD_DISPLAY_ON)

    # ── Public API ────────────────────────────────────────────────────

    def show(self, oled: OLEDBuffer):
        """
        Flush an OLEDBuffer to the physical display.
        Call this once per frame after all drawing is done.
        """
        # Set full-screen column and page window
        self._cmd(_CMD_SET_COL_ADDR,  0, OLEDBuffer.WIDTH - 1)
        self._cmd(_CMD_SET_PAGE_ADDR, 0, (OLEDBuffer.HEIGHT // 8) - 1)
        self._data(oled.to_ssd1309_bytes())

    def clear(self):
        """Blank the display (without touching the OLEDBuffer object)."""
        self._cmd(_CMD_SET_COL_ADDR,  0, OLEDBuffer.WIDTH - 1)
        self._cmd(_CMD_SET_PAGE_ADDR, 0, (OLEDBuffer.HEIGHT // 8) - 1)
        self._data(bytes(OLEDBuffer.WIDTH * OLEDBuffer.HEIGHT // 8))

    def set_contrast(self, value: int):
        """Adjust brightness (0x00–0xFF)."""
        self._cmd(_CMD_SET_CONTRAST, value & 0xFF)

    def display_on(self):
        self._cmd(_CMD_DISPLAY_ON)

    def display_off(self):
        self._cmd(_CMD_DISPLAY_OFF)

    def invert(self, enabled: bool):
        self._cmd(0xA7 if enabled else _CMD_NORMAL_DISPLAY)

    def cleanup(self):
        """Release SPI and GPIO resources."""
        self.display_off()
        self._spi.close()
        GPIO.cleanup()
