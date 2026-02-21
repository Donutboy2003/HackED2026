"""Converts raw roll/pitch into one of 9 directions + dwell timing."""

import math
import time

# Deadzone radius (magnitude below this = CENTER)
DEADZONE_RADIUS = 0.12

# Dead band: half-width in degrees on each side of a sector boundary
DEAD_BAND_DEG = 10.0

# Direction constants
DIR_CENTER = "CENTER"
DIR_N = "N"
DIR_NE = "NE"
DIR_E = "E"
DIR_SE = "SE"
DIR_S = "S"
DIR_SW = "SW"
DIR_W = "W"
DIR_NW = "NW"

# Ordered by angle (0° = East, counter-clockwise)
_DIRECTIONS = [
    (0.0, DIR_E),
    (45.0, DIR_NE),
    (90.0, DIR_N),
    (135.0, DIR_NW),
    (180.0, DIR_W),
    (225.0, DIR_SW),
    (270.0, DIR_S),
    (315.0, DIR_SE),
]

CARDINALS = {DIR_N, DIR_S, DIR_E, DIR_W}
DIAGONALS = {DIR_NE, DIR_NW, DIR_SE, DIR_SW}


def _snap_direction(roll: float, pitch: float) -> str:
    """Return one of 9 direction constants from roll/pitch."""
    mag = math.sqrt(roll * roll + pitch * pitch)
    if mag < DEADZONE_RADIUS:
        return DIR_CENTER

    # atan2 with pitch as Y (up = north), roll as X (right = east)
    angle_rad = math.atan2(pitch, -roll)
    angle_deg = math.degrees(angle_rad) % 360.0

    for center_deg, direction in _DIRECTIONS:
        dist = abs(((angle_deg - center_deg) + 180.0) % 360.0 - 180.0)
        if dist <= (22.5 - DEAD_BAND_DEG):
            return direction

    return DIR_CENTER  # in a dead band


class InputProcessor:
    def __init__(self):
        self.direction = DIR_CENTER
        self.magnitude = 0.0
        self.roll = 0.0
        self.pitch = 0.0

        # Dwell
        self._current_dir = DIR_CENTER
        self._dwell_start = time.time()
        self.dwell_seconds = 0.0

    def update(self, roll: float, pitch: float):
        """Call once per frame. Updates direction, magnitude, dwell time."""
        now = time.time()
        self.roll = roll
        self.pitch = pitch
        self.magnitude = math.sqrt(roll * roll + pitch * pitch)
        self.direction = _snap_direction(roll, pitch)

        if self.direction != self._current_dir:
            self._current_dir = self.direction
            self._dwell_start = now
            self.dwell_seconds = 0.0
        else:
            self.dwell_seconds = now - self._dwell_start

    def reset_dwell(self):
        """Call after an action fires to restart the timer."""
        self._dwell_start = time.time()
        self.dwell_seconds = 0.0
