"""Non-blocking text-to-speech via a background worker thread (Piper TTS backend)."""

import queue
import threading
import subprocess
import logging

log = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

MODEL_PATH       = "/home/byteof87/dev/HackED2026/text_to_speech/en_US-lessac-medium.onnx"
PIPER_EXECUTABLE = "piper"
AUDIO_PLAYER     = "pacat"
SPEECH_RATE  = 1.3
LATENCY_MSEC = 500

# ── Low-level speak ────────────────────────────────────────────────────────────

def _speak_now(text: str, model_path: str = MODEL_PATH) -> None:
    """Blocking: synthesise and play one utterance via Piper → pacat."""
    piper_cmd = [PIPER_EXECUTABLE, "--model", model_path, "--output_raw","--length-scale", str(SPEECH_RATE),]
    player_cmd = [
        AUDIO_PLAYER, "--raw",
        "--rate=22050", "--format=s16le", "--channels=1",f"--latency-msec={LATENCY_MSEC}",
    ]
    try:
        piper_proc = subprocess.Popen(
            piper_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        player_proc = subprocess.Popen(
            player_cmd,
            stdin=piper_proc.stdout,
            stderr=subprocess.DEVNULL,
        )

        piper_proc.stdin.write(text.encode("utf-8"))
        piper_proc.stdin.close()
        piper_proc.stdout.close()
        player_proc.wait()

    except FileNotFoundError:
        log.error("Piper or pacat not found. Check PIPER_EXECUTABLE / AUDIO_PLAYER.")
    except Exception as e:
        log.error("TTS error: %s", e)


# ── Public interface (matches original tts.py) ─────────────────────────────────

class TTSQueue:
    def __init__(self, model_path: str = MODEL_PATH):
        self._model  = model_path
        self._q      = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        log.info("TTSQueue ready (Piper backend)")

    def speak(self, text: str) -> None:
        """Enqueue a message. Returns immediately."""
        text = text.strip()
        if not text:
            return
        log.info("TTS enqueue: %r", text)
        self._q.put(text)

    def clear(self) -> None:
        """Discard all pending phrases."""
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

    def _worker(self) -> None:
        while True:
            text = self._q.get()
            try:
                log.debug("TTS speaking: %r", text)
                _speak_now(text, model_path=self._model)
            except Exception as e:
                log.error("TTS worker error: %s", e)
