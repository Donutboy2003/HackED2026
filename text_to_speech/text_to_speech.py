"""
Piper TTS - Text to Speech Module (Low Latency)
=================================================
Uses Piper's Python API directly to keep the model loaded in memory,
avoiding the lag caused by reloading the model on every speak() call.
Audio is synthesized to an in-memory buffer — no disk I/O.
"""

import io
import queue
import threading
import wave
import platform
import subprocess

from piper.voice import PiperVoice

# ── Configuration ──────────────────────────────────────────────────────────────

MODEL_PATH = "/home/byteof87/dev/HackED2026/text_to_speech/en_US-lessac-medium.onnx"

# ── Load model ONCE at startup ─────────────────────────────────────────────────

print("[TTS] Loading voice model... ", end="", flush=True)
_voice = PiperVoice.load(MODEL_PATH)
print("done.")

# ── Core TTS Function ──────────────────────────────────────────────────────────

# def speak(text: str) -> None:
#     """
#     Convert text to speech and play it.
#     Model is loaded in memory and audio is buffered in memory — no disk I/O.
#     """
#     if not text.strip():
#         return

#     try:
#         # Synthesize into an in-memory buffer (no temp file)
#         buffer = io.BytesIO()
#         with wave.open(buffer, "wb") as wav_file:
#             wav_file.setnchannels(1)
#             wav_file.setsampwidth(2)
#             wav_file.setframerate(_voice.config.sample_rate)
#             _voice.synthesize(text, wav_file)

#         # Pipe buffer directly to audio player
#         buffer.seek(0)
#         if platform.system() == "Darwin":
#             subprocess.run(["afplay", "-"], input=buffer.read(), stderr=subprocess.DEVNULL)
#         else:
#             subprocess.run(["aplay", "-"], input=buffer.read(), stderr=subprocess.DEVNULL)

#     except Exception as e:
#         print(f"[ERROR] TTS failed: {e}")

def speak(text: str) -> None:
    if not text.strip():
        return

    try:
        # Get raw PCM audio chunks directly
        raw_audio = b"".join(_voice.synthesize_stream_raw(text))

        # Play raw PCM with explicit format flags
        if platform.system() == "Darwin":
            # Save to temp file for Mac (afplay needs a proper file)
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(_voice.config.sample_rate)
                wav_file.writeframes(raw_audio)
            with open(tmp_path, "wb") as f:
                f.write(buffer.getvalue())
            subprocess.run(["afplay", tmp_path])
            os.remove(tmp_path)
        else:
            # Linux/Pi: pipe raw PCM directly to aplay
            subprocess.run([
                "aplay",
                "-r", str(_voice.config.sample_rate),
                "-f", "S16_LE",
                "-c", "1",
                "-t", "raw",
                "-"
            ], input=raw_audio, stderr=subprocess.DEVNULL)

    except Exception as e:
        print(f"[ERROR] TTS failed: {e}")

# ── Queued / Non-blocking TTS ──────────────────────────────────────────────────

class TTSQueue:
    """
    Non-blocking TTS queue — speak() runs in a background thread
    so typing is never blocked while audio is playing.
    """

    def __init__(self):
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def say(self, text: str) -> None:
        """Add text to the speech queue (non-blocking)."""
        if text.strip():
            self._queue.put(text)

    def clear(self) -> None:
        """Clear any pending phrases from the queue."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _worker(self) -> None:
        while True:
            text = self._queue.get()
            speak(text)
            self._queue.task_done()


# ── Interactive CLI ────────────────────────────────────────────────────────────

def interactive_mode() -> None:
    print("=" * 50)
    print("  Piper TTS - Assistive Communication Tool")
    print("=" * 50)
    print("  Type your message and press Enter to speak.")
    print("  Commands: :quit, :clear")
    print("=" * 50)

    tts = TTSQueue()

    while True:
        try:
            user_input = input("\n> ").strip()

            if not user_input:
                continue
            elif user_input.lower() == ":quit":
                print("Goodbye!")
                break
            elif user_input.lower() == ":clear":
                tts.clear()
                print("[Queue cleared]")
            else:
                tts.say(user_input)
                print(f"[Speaking] {user_input}")

        except KeyboardInterrupt:
            print("\nExiting.")
            break


if __name__ == "__main__":
    interactive_mode()