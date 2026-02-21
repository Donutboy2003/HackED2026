"""
Piper TTS - Text to Speech Module
===================================
Uses Piper TTS for high-quality offline speech synthesis.

Setup (run once on your Raspberry Pi):
    pip install piper-tts
    # Models will be downloaded automatically on first use,
    # or manually download from: https://huggingface.co/rhasspy/piper-voices

Usage:
    python tts_piper.py
"""

import subprocess
import tempfile
import os
import sys
import queue
import threading

# ── Configuration ──────────────────────────────────────────────────────────────

# Path to your downloaded Piper voice model (.onnx file)
# Download voices from: https://huggingface.co/rhasspy/piper-voices
# Recommended voices for clarity:
#   en_US-lessac-medium    (natural, balanced)
#   en_US-ryan-high        (high quality, slower)
#   en_US-amy-medium       (clear, good for accessibility)
MODEL_PATH = "en_US-lessac-medium.onnx"

# Piper executable path (if not in PATH, provide full path)
PIPER_EXECUTABLE = "piper"

# Audio playback command (aplay for Linux/Raspberry Pi)
AUDIO_PLAYER = "aplay"

# ── Core TTS Function ──────────────────────────────────────────────────────────

def speak(text: str, model_path: str = MODEL_PATH) -> None:
    """
    Convert text to speech and play it immediately using Piper TTS.

    Parameters:
        text (str): The text to be spoken.
        model_path (str): Path to the .onnx Piper voice model.
    """
    if not text.strip():
        return

    try:
        # Piper reads from stdin and outputs raw audio,
        # which we pipe directly into aplay for playback.
        piper_cmd = [PIPER_EXECUTABLE, "--model", model_path, "--output_raw"]
        player_cmd = [AUDIO_PLAYER, "--rate=22050", "--format=S16_LE",
                      "--channels=1", "-"]

        piper_proc = subprocess.Popen(
            piper_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )
        player_proc = subprocess.Popen(
            player_cmd,
            stdin=piper_proc.stdout,
            stderr=subprocess.DEVNULL
        )

        piper_proc.stdin.write(text.encode("utf-8"))
        piper_proc.stdin.close()
        piper_proc.stdout.close()
        player_proc.wait()

    except FileNotFoundError:
        print("[ERROR] Piper or aplay not found. Check installation.")
        print("        Install Piper: pip install piper-tts")
        print("        Install aplay: sudo apt install alsa-utils")
    except Exception as e:
        print(f"[ERROR] TTS failed: {e}")


def speak_to_file(text: str, output_path: str, model_path: str = MODEL_PATH) -> bool:
    """
    Convert text to speech and save it as a .wav file instead of playing it.

    Parameters:
        text (str): The text to convert.
        output_path (str): Path to save the .wav file.
        model_path (str): Path to the .onnx Piper voice model.

    Returns:
        bool: True if successful, False otherwise.
    """
    if not text.strip():
        return False

    try:
        piper_cmd = [PIPER_EXECUTABLE, "--model", model_path,
                     "--output_file", output_path]

        result = subprocess.run(
            piper_cmd,
            input=text.encode("utf-8"),
            capture_output=True
        )
        return result.returncode == 0

    except Exception as e:
        print(f"[ERROR] Failed to save audio: {e}")
        return False


# ── Queued / Non-blocking TTS ──────────────────────────────────────────────────

class TTSQueue:
    """
    A non-blocking TTS queue so the UI stays responsive while speech plays.
    Phrases are spoken in order, one at a time.
    """

    def __init__(self, model_path: str = MODEL_PATH):
        self.model_path = model_path
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
            speak(text, model_path=self.model_path)
            self._queue.task_done()


# ── Interactive CLI Demo ───────────────────────────────────────────────────────

def interactive_mode() -> None:
    """
    Simple interactive CLI — type text and press Enter to hear it spoken.
    This simulates the core feature for the deaf/mute assistive tool.
    """
    print("=" * 50)
    print("  Piper TTS - Assistive Communication Tool")
    print("=" * 50)
    print(f"  Model : {MODEL_PATH}")
    print("  Type your message and press Enter to speak.")
    print("  Commands: :quit, :clear")
    print("=" * 50)

    tts = TTSQueue(model_path=MODEL_PATH)

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


# ── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    interactive_mode()