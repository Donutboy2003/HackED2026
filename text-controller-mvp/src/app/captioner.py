"""Mock live captioning module. Replace internals with real speech engine later."""

import time

_SAMPLE_PHRASES = [
    "THE QUICK BROWN FOX",
    "JUMPED OVER THE LAZY DOG",
    "HELLO HOW ARE YOU TODAY",
    "THIS IS A LIVE CAPTION TEST",
    "SPEECH RECOGNITION IS RUNNING",
    "THE WEATHER IS NICE OUTSIDE",
]


class Captioner:
    def __init__(self):
        self.transcript: list[str] = []
        self.paused = False
        self._next_phrase_time = time.time() + 3.0
        self._phrase_index = 0

    def update(self):
        """Simulate incoming captions on a timer."""
        if self.paused:
            return
        now = time.time()
        if now >= self._next_phrase_time:
            phrase = _SAMPLE_PHRASES[self._phrase_index % len(_SAMPLE_PHRASES)]
            self.transcript.append(phrase)
            self._phrase_index += 1
            self._next_phrase_time = now + 4.0

    def toggle_pause(self):
        self.paused = not self.paused

    def clear(self):
        self.transcript.clear()

    def get_last_word(self) -> str:
        """Return the last word of the transcript for quick-edit bridge."""
        if not self.transcript:
            return ""
        words = self.transcript[-1].split()
        return words[-1] if words else ""
