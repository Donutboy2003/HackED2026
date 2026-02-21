import pyaudio
import numpy as np
import webrtcvad
import collections
import wave
import tempfile
import os
from faster_whisper import WhisperModel

# ── Settings ──────────────────────────────────────────────
MODEL_SIZE    = "base"      # tiny, base, small (stick to tiny/base for Pi)
SAMPLE_RATE   = 16000       # Whisper requires 16kHz
CHUNK_MS      = 30          # VAD works in 10, 20, or 30ms chunks
CHUNK_SIZE    = int(SAMPLE_RATE * CHUNK_MS / 1000)  # samples per chunk
VAD_MODE      = 3           # 0=least aggressive, 3=most aggressive (filters noise)
SILENCE_LIMIT = 1.5         # seconds of silence before we consider speech done
PADDING       = 0.3         # seconds of audio to keep before speech starts
# ──────────────────────────────────────────────────────────

def save_temp_wav(frames):
    temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wf = wave.open(temp.name, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    return temp.name

def transcribe(model, path):
    segments, _ = model.transcribe(
        path,
        language="en",
        beam_size=5,
        vad_filter=True   # faster-whisper also has a built-in VAD as a second layer
    )
    return " ".join([seg.text for seg in segments]).strip()

def main():
    # Load faster-whisper model
    print(f"Loading faster-whisper '{MODEL_SIZE}' model...")
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    print("Model loaded!\n")

    # Set up VAD
    vad = webrtcvad.Vad(VAD_MODE)

    # Set up PyAudio
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK_SIZE
    )

    # Ring buffer holds recent audio so we don't miss the start of speech
    padding_chunks  = int(PADDING * 1000 / CHUNK_MS)
    silence_chunks  = int(SILENCE_LIMIT * 1000 / CHUNK_MS)
    ring_buffer     = collections.deque(maxlen=padding_chunks)

    print("Listening... (Press Ctrl+C to stop)\n")

    triggered       = False   # are we currently recording speech?
    voiced_frames   = []      # frames that contain speech
    silence_counter = 0       # how many consecutive silent chunks we've seen

    try:
        while True:
            chunk = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            is_speech = vad.is_speech(chunk, SAMPLE_RATE)

            if not triggered:
                # Not yet recording — keep a rolling buffer of recent audio
                ring_buffer.append(chunk)

                if is_speech:
                    # Speech detected — start recording
                    triggered = True
                    silence_counter = 0
                    print("Speech detected...")

                    # Include the buffered audio before speech started
                    voiced_frames.extend(ring_buffer)
                    ring_buffer.clear()

            else:
                # Currently recording
                voiced_frames.append(chunk)

                if not is_speech:
                    silence_counter += 1
                else:
                    silence_counter = 0

                # If we've seen enough silence, the person has stopped speaking
                if silence_counter > silence_chunks:
                    print("Silence detected, transcribing...")
                    triggered = False
                    silence_counter = 0

                    # Save and transcribe
                    temp_path = save_temp_wav(voiced_frames)
                    text = transcribe(model, temp_path)
                    os.remove(temp_path)

                    voiced_frames = []

                    if text:
                        print(f"Transcribed: {text}\n")
                    else:
                        print("(no speech detected)\n")

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    main()