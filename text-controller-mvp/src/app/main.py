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

CENTER_HOLD_SEC    = 3.0   # time for user to return to center
CALIBRATION_SEC    = 2.0   # matches sensor binary calibration window


def _run_calibration(driver: SSD1309Driver, oled: OLEDBuffer, reader: SerialReader):
    """Block the main loop, show calibration UI, restart sensor."""

    # Phase 1 — prompt user to center
    deadline = time.time() + CENTER_HOLD_SEC
    while time.time() < deadline:
        remaining = (deadline - time.time()) / CENTER_HOLD_SEC
        oled.clear()
        oled.draw_calibration_scene(phase="center", countdown=remaining)
        driver.show(oled)
        time.sleep(0.05)

    # Restart the subprocess — it will immediately begin its own calibration
    reader.restart()

    # Phase 2 — show calibration in progress
    deadline = time.time() + CALIBRATION_SEC
    while time.time() < deadline:
        remaining = (deadline - time.time()) / CALIBRATION_SEC
        oled.clear()
        oled.draw_calibration_scene(phase="calibrating", countdown=remaining)
        driver.show(oled)
        time.sleep(0.05)



def main():
    reader = SerialReader(SERIAL_PORT, BAUD_RATE)
    state = AppState()
    state.on_restart_sensor = reader.restart
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

    # Initial calibration run on startup
    _run_calibration(driver, oled, reader)

    if not reader.connect():
        print(f"Serial error: {reader.last_error}")
        driver.cleanup()
        sys.exit(1)

    print("Running — press Ctrl-C to stop.")

    while True:
        # Handle restart request from app_state
        if state.restart_requested:
            state.restart_requested = False
            _run_calibration(driver, oled, reader)
            continue

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
                    direction=inp.direction,
                    dwell_percent=s.dwell_percent,
                )

            driver.show(oled)

        time.sleep(LOOP_DELAY_S)


if __name__ == "__main__":
    main()
