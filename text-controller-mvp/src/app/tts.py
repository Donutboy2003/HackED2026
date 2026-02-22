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
LENGTH_SCALE     = 1.3    # >1.0 = slower, <1.0 = faster (Piper --length-scale)
LATENCY_MSEC     = 500
PIPER_TIMEOUT    = 15     # seconds before piper synthesis is considered hung
PLAYER_TIMEOUT   = 30     # seconds before pacat playback is considered hung


# ── Low-level speak ────────────────────────────────────────────────────────────

def _speak_now(text: str, model_path: str = MODEL_PATH) -> None:
    """Blocking: synthesise and play one utterance via Piper → pacat."""
    piper_cmd = [
        PIPER_EXECUTABLE,
        "--model",        model_path,
        "--output_raw",
        "--length-scale", str(LENGTH_SCALE),
    ]
    player_cmd = [
        AUDIO_PLAYER,
        "--raw",
        "--rate=22050",
        "--format=s16le",
        "--channels=1",
        f"--latency-msec={LATENCY_MSEC}",
    ]

    piper_proc  = None
    player_proc = None

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

        try:
            piper_proc.wait(timeout=PIPER_TIMEOUT)
            player_proc.wait(timeout=PLAYER_TIMEOUT)
        except subprocess.TimeoutExpired:
            log.error("TTS timed out — killing processes")
            piper_proc.kill()
            player_proc.kill()

    except FileNotFoundError:
        log.error("Piper or pacat not found. Check PIPER_EXECUTABLE / AUDIO_PLAYER.")
    except Exception as e:
        log.error("TTS error: %s", e)
    finally:
        # Always clean up stdout fd regardless of how we exited
        if piper_proc and piper_proc.stdout:
            piper_proc.stdout.close()


# ── Public interface ───────────────────────────────────────────────────────────

class TTSQueue:
    def __init__(self, model_path: str = MODEL_PATH):
        self._model  = model_path
        self._q      = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        log.info("TTSQueue ready (Piper backend, model=%s)", model_path)

    def speak(self, text: str) -> None:
        """Enqueue a message. Returns immediately."""
        text = text.strip()
        if not text:
            return
        log.info("TTS enqueue: %r", text)
        self._q.put(text)

    def clear(self) -> None:
        """Discard all pending queued phrases (does not interrupt current speech)."""
        with self._q.mutex:
            self._q.queue.clear()
        log.debug("TTS queue cleared")

    def _worker(self) -> None:
        while True:
            text = self._q.get()
            try:
                log.debug("TTS speaking: %r", text)
                _speak_now(text, model_path=self._model)
            except Exception as e:
                log.error("TTS worker error: %s", e)
