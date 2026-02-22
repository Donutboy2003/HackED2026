"""Reads roll,pitch lines from the local sensor binary via subprocess."""

import subprocess
import threading
from pathlib import Path

SENSOR_BINARY = Path(__file__).parent.parent / "sensor" / "sensor"


class SerialReader:
    def __init__(self, _port=None, _baud=None):
        # _port and _baud are ignored — kept for API compatibility
        self._proc   = None
        self._latest = None
        self._lock   = threading.Lock()
        self._thread = None
        self.last_error = ""

    def connect(self) -> bool:
        if not SENSOR_BINARY.exists():
            self.last_error = f"Sensor binary not found: {SENSOR_BINARY}"
            return False
        try:
            self._proc = subprocess.Popen(
                [str(SENSOR_BINARY)],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,   # suppress calibration prints
                text=True,
                bufsize=1,                   # line-buffered
            )
        except OSError as e:
            self.last_error = str(e)
            return False

        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        return True

    def _read_loop(self):
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                roll, pitch = map(float, line.split(","))
                with self._lock:
                    self._latest = (roll, pitch)
            except ValueError:
                pass

    def read_latest(self):
        with self._lock:
            val = self._latest
            self._latest = None
            return val

    def close(self):
        if self._proc:
            self._proc.terminate()
            self._proc.wait()
