import time
import lgpio
import spidev

PIN_DC  = 24
PIN_RST = 25
SPI_BUS = 0
SPI_DEV = 0
SPI_MAX_SPEED_HZ = 8_000_000

# RPi5 uses gpiochip4; RPi4 and earlier use gpiochip0
GPIO_CHIP = 4


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

        # ── lgpio setup ───────────────────────────────────────────────
        self._h = lgpio.gpiochip_open(gpio_chip)
        lgpio.gpio_claim_output(self._h, self._dc)
        lgpio.gpio_claim_output(self._h, self._rst)

        # ── SPI setup ─────────────────────────────────────────────────
        self._spi = spidev.SpiDev()
        self._spi.open(spi_bus, spi_dev)
        self._spi.max_speed_hz = spi_speed_hz
        self._spi.mode = 0b00

        self._reset()
        self._init_sequence(contrast)

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
        # (identical to the previous version — no changes here)
        ...

    def show(self, oled):
        self._cmd(0x21, 0, 127)
        self._cmd(0x22, 0, 7)
        self._data(oled.to_ssd1309_bytes())

    def clear(self):
        self._cmd(0x21, 0, 127)
        self._cmd(0x22, 0, 7)
        self._data(bytes(128 * 64 // 8))

    def set_contrast(self, value: int):
        self._cmd(0x81, value & 0xFF)

    def display_on(self):  self._cmd(0xAF)
    def display_off(self): self._cmd(0xAE)

    def cleanup(self):
        self.display_off()
        self._spi.close()
        lgpio.gpiochip_close(self._h)
