"""Reads filtered roll/pitch from the Pico over serial."""

import serial


class SerialReader:
    def __init__(self, port: str, baud: int):
        self.ser = None
        self.port = port
        self.baud = baud
        self.last_error = None

    def connect(self) -> bool:
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0)
            self.last_error = None
            return True
        except Exception as e:
            self.last_error = str(e)
            return False

    def read_latest(self) -> tuple[float, float] | None:
        """Return the most recent (roll, pitch) or None."""
        if not self.ser:
            return None
        try:
            lines = self.ser.readlines()
            if not lines:
                return None
            last_line = lines[-1].decode("utf-8", errors="ignore").strip()
            if "," not in last_line:
                return None
            parts = last_line.split(",")
            if len(parts) < 2:
                return None
            return float(parts[0]), float(parts[1])
        except Exception:
            return None
