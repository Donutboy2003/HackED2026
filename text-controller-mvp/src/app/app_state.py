"""Central state machine. Routes direction events to mode-specific logic."""

import time
from input_processor import (
    InputProcessor, CARDINALS, DIAGONALS,
    DIR_CENTER, DIR_N, DIR_S, DIR_E, DIR_W,
    DIR_NE, DIR_NW, DIR_SE, DIR_SW,
)
from predictor import PredictiveText
from captioner import Captioner
from font import ALPHABET
from tty import TTSQueue

MODE_WRITE = "WRITE"
MODE_CAPTION = "CAPTION"

# Dwell thresholds
DWELL_CENTER_SEC = 3.0
DWELL_DIAGONAL_SEC = 2.0

# Cardinal repeat rate
SCROLL_COOLDOWN_SEC = 0.5

# Grace period after returning to center (cancel gesture)
CENTER_COOLDOWN_SEC = 1.0


class AppState:
    def __init__(self):
        self.mode = MODE_CAPTION
        self.input = InputProcessor()
        self.predictor = PredictiveText()
        self.captioner = Captioner()
        self.tts = TTSQueue()

        # Write mode state
        self.sentence = ""
        self.prefix = ""
        self.cursor_index = 0
        self.sugg_index = 0  # 0 = alphabet, 1..3 = suggestion slots
        self.suggestions: list[str] = []

        # N-gram debug info
        self.ngram_level: str = "—"        # "5G", "4G", "3G", "2G", "1G", or "—"
        self.ngram_context: str = ""       # the word(s) used as lookup key

        # Caption mode state
        self.transcript_scroll = 0

        # Scroll repeat tracking
        self._last_scroll_time = 0.0

        # Diagonal action lock
        self._diagonal_fired = False

        # Feedback flash
        self.flash_direction: str | None = None
        self._flash_end = 0.0

        # Center dwell cooldown
        self._center_cooldown_until = 0.0
        self._was_off_center = False

    # ------------------------------------------------------------------
    @property
    def dwell_percent(self) -> float:
        d = self.input.direction
        now = time.time()
        if d == DIR_CENTER:
            if self.mode == MODE_CAPTION:
                return 0.0
            if now < self._center_cooldown_until:
                return 0.0
            remaining_cooldown = max(0, self._center_cooldown_until - (now - self.input.dwell_seconds))
            active_time = self.input.dwell_seconds - remaining_cooldown
            return min(1.0, max(0.0, active_time / DWELL_CENTER_SEC))
        if d in DIAGONALS:
            return min(1.0, self.input.dwell_seconds / DWELL_DIAGONAL_SEC)
        return 0.0

    # ------------------------------------------------------------------
    def update(self, roll: float, pitch: float):
        now = time.time()
        self.input.update(roll, pitch)
        d = self.input.direction

        # Clear flash
        if now > self._flash_end:
            self.flash_direction = None

        # Track center cooldown
        if d != DIR_CENTER:
            self._was_off_center = True
        elif self._was_off_center:
            self._was_off_center = False
            self._center_cooldown_until = now + CENTER_COOLDOWN_SEC
            self.input.reset_dwell()

        # Reset diagonal lock when direction changes
        if d != self._diagonal_fired:
            self._diagonal_fired = False

        # Update suggestions for write mode
        if self.mode == MODE_WRITE:
            self.suggestions, self.ngram_level, self.ngram_context = (
                self.predictor.get_suggestions(
                    self.prefix, context=self.sentence, max_results=3
                )
            )

        # Update captioner
        if self.mode == MODE_CAPTION:
            self.captioner.update()

        # --- Dispatch ---
        if d == DIR_CENTER:
            self._handle_center(now)
        elif d in CARDINALS:
            self._handle_cardinal(d, now)
        elif d in DIAGONALS:
            self._handle_diagonal(d)

    # ------------------------------------------------------------------
    def _handle_center(self, now):
        if now < self._center_cooldown_until:
            return
        if self.mode == MODE_WRITE and self.dwell_percent >= 1.0:
            self._select_current()
            self.input.reset_dwell()
            self._center_cooldown_until = now + CENTER_COOLDOWN_SEC

    def _handle_cardinal(self, d: str, now: float):
        if now - self._last_scroll_time < SCROLL_COOLDOWN_SEC:
            return
        self._last_scroll_time = now

        if self.mode == MODE_WRITE:
            if d == DIR_E:
                self.cursor_index = (self.cursor_index + 1) % len(ALPHABET)
            elif d == DIR_W:
                self.cursor_index = (self.cursor_index - 1) % len(ALPHABET)
            elif d == DIR_S:
                self.sugg_index = min(self.sugg_index + 1, len(self.suggestions))
            elif d == DIR_N:
                self.sugg_index = max(self.sugg_index - 1, 0)

        elif self.mode == MODE_CAPTION:
            if d == DIR_N:
                self.transcript_scroll = min(
                    self.transcript_scroll + 1,
                    max(0, len(self.captioner.transcript) - 1),
                )
            elif d == DIR_S:
                self.transcript_scroll = max(self.transcript_scroll - 1, 0)

    def _handle_diagonal(self, d: str):
        if self._diagonal_fired:
            return
        if self.dwell_percent < 1.0:
            return

        self._diagonal_fired = d
        self.input.reset_dwell()
        self._flash(d)

        if d == DIR_NW:
            if self.mode == MODE_WRITE:
                self.mode = MODE_CAPTION
            else:
                self.mode = MODE_WRITE

        elif self.mode == MODE_WRITE:
            if d == DIR_NE:
                self._accept_top_suggestion()
            elif d == DIR_SE:
                self._backspace()
            elif d == DIR_SW:
                self._delete_word()

        elif self.mode == MODE_CAPTION:
            if d == DIR_NE:
                word = self.captioner.get_last_word()
                if word:
                    self.prefix = word
                    self.mode = MODE_WRITE
            elif d == DIR_SE:
                self.captioner.toggle_pause()
            elif d == DIR_SW:
                self.captioner.clear()
                self.transcript_scroll = 0

    # ------------------------------------------------------------------
    # Write-mode actions
    # ------------------------------------------------------------------
    def _select_current(self):
        if self.sugg_index == 0:
            char = ALPHABET[self.cursor_index % len(ALPHABET)]
            if char == "_":
                self.sentence += self.prefix + " "
                self.prefix = ""
            elif char == "<":
                self._backspace()
            elif char == "[":
                self._delete_word()
            elif char == "]":
                self.sentence = ""
                self.prefix = ""
            elif char == ".":  # TTS trigger
                self._send_message()
            else:
                self.prefix += char
        else:
            idx = self.sugg_index - 1
            if 0 <= idx < len(self.suggestions):
                self.sentence += self.suggestions[idx] + " "
                self.prefix = ""
            self.sugg_index = 0

    def _accept_top_suggestion(self):
        if self.suggestions:
            self.sentence += self.suggestions[0] + " "
            self.prefix = ""
            self.sugg_index = 0

    def _backspace(self):
        if self.prefix:
            self.prefix = self.prefix[:-1]
        elif self.sentence:
            self.sentence = self.sentence[:-1]

    def _delete_word(self):
        if self.prefix:
            self.prefix = ""
        else:
            words = self.sentence.strip().split(" ")
            if words and words != [""]:
                self.sentence = " ".join(words[:-1])
                if self.sentence:
                    self.sentence += " "
            else:
                self.sentence = ""

    def _send_message(self):
        """Commit prefix, speak the full sentence, then clear."""
        if self.prefix:
            self.sentence += self.prefix + " "
            self.prefix = ""
        message = self.sentence.strip()
        if not message:
            return
        log.info("Sending message: %r", message)
        self.tts.speak(message)
        self.sentence = ""
        self.sugg_index = 0
        self._flash(".")

    def _flash(self, direction: str):
        self.flash_direction = direction
        self._flash_end = time.time() + 0.3
