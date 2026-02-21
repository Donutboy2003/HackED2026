"""Entry point — headless loop driving the physical SSD1309 OLED."""

import time
import signal
import sys

from serial_reader import SerialReader
from app_state import AppState, MODE_WRITE
from oled_driver import OLEDBuffer, SSD1309Driver

SERIAL_PORT = "/dev/tty.usbmodem1102"
BAUD_RATE = 115200
LOOP_DELAY_S = 0.016   # ~60 fps


def main():
    reader = SerialReader(SERIAL_PORT, BAUD_RATE)
    state = AppState()
    oled = OLEDBuffer()
    driver = SSD1309Driver()

    # Graceful shutdown on Ctrl-C or SIGTERM
    def _shutdown(sig=None, frame=None):
        print("\nShutting down…")
        driver.clear()
        driver.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    if not reader.connect():
        print(f"Serial error: {reader.last_error}")
        driver.cleanup()
        sys.exit(1)

    print("Running — press Ctrl-C to stop.")

    while True:
        data = reader.read_latest()
        if data is not None:
            roll, pitch = data
            state.update(roll, pitch)

            s = state
            inp = s.input

            oled.clear()
            if s.mode == MODE_WRITE:
                oled.draw_write_scene(
                    sentence=s.sentence,
                    prefix=s.prefix,
                    cursor_index=s.cursor_index,
                    sugg_index=s.sugg_index,
                    suggestions=s.suggestions,
                    dwell_percent=s.dwell_percent,
                    direction=inp.direction,
                )
            else:
                oled.draw_caption_scene(
                    transcript=s.captioner.transcript,
                    scroll_offset=s.transcript_scroll,
                    paused=s.captioner.paused,
                )

            driver.show(oled)

        time.sleep(LOOP_DELAY_S)


if __name__ == "__main__":
    main()
