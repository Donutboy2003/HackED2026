"""Live captioning module powered by Vosk offline speech recognition.

Audio capture runs on a background thread so the recognizer is always fed
continuously, regardless of how fast the main app loop calls update().
"""

import json
import queue
import threading

import pyaudio
import vosk

MODEL_PATH = "vosk-model-small-en-us-0.15"

_RATE = 16000
_CHUNK = 4000


class Captioner:
    def __init__(self, model_path: str = MODEL_PATH):
        print("Loading Vosk model...")
        model = vosk.Model(model_path)
        self.recognizer = vosk.KaldiRecognizer(model, _RATE)

        self.transcript: list[str] = []
        self.partial: str = ""
        self.paused = False

        self._audio_queue: queue.Queue[bytes] = queue.Queue()
        self._stop_event = threading.Event()

        # PyAudio callback mode — audio is captured on its own thread automatically
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=_RATE,
            input=True,
            frames_per_buffer=_CHUNK,
            stream_callback=self._audio_callback,
        )

        # Vosk recognition runs on a second background thread
        self._thread = threading.Thread(target=self._recognition_loop, daemon=True)
        self._thread.start()

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio calls this whenever a chunk is ready — never blocks the app."""
        if not self.paused:
            self._audio_queue.put(in_data)
        return (None, pyaudio.paContinue)

    def _recognition_loop(self):
        """Continuously drain the audio queue and run Vosk recognition."""
        while not self._stop_event.is_set():
            try:
                data = self._audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if self.recognizer.AcceptWaveform(data):
                result = json.loads(self.recognizer.Result())
                text = result.get("text", "").upper()
                if text:
                    self.transcript.append(text)
                    self.partial = ""
            else:
                partial = json.loads(self.recognizer.PartialResult())
                self.partial = partial.get("partial", "").upper()

    def update(self):
        """No-op — recognition now happens continuously in the background.

        Keep calling this if your existing code expects it; results are always
        available via self.transcript and self.partial.
        """
        pass

    def toggle_pause(self):
        self.paused = not self.paused

    def clear(self):
        self.transcript.clear()
        self.partial = ""

    def get_last_word(self) -> str:
        """Return the last confirmed word from the transcript."""
        if not self.transcript:
            return ""
        words = self.transcript[-1].split()
        return words[-1] if words else ""

    def close(self):
        """Stop background threads and release audio resources."""
        self._stop_event.set()
        self._thread.join(timeout=2)
        self._stream.stop_stream()
        self._stream.close()
        self._pa.terminate()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
