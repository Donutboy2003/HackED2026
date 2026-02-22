"""Non-blocking text-to-speech via a background worker thread."""

import queue
import threading
import logging
import pyttsx3

log = logging.getLogger(__name__)


class TTSQueue:
    def __init__(self):
        self._q      = queue.Queue()
        self._engine = pyttsx3.init()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        log.info("TTSQueue ready")

    def speak(self, text: str):
        """Enqueue a message. Returns immediately."""
        text = text.strip()
        if not text:
            return
        log.info("TTS enqueue: %r", text)
        self._q.put(text)

    def _worker(self):
        while True:
            text = self._q.get()
            try:
                log.debug("TTS speaking: %r", text)
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as e:
                log.error("TTS error: %s", e)
