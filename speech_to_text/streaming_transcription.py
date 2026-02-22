import sys
from unittest.mock import MagicMock

# pvporcupine (wake word engine) doesn't support this ARM CPU variant.
# Since we're not using wake words, we can safely mock it out.
sys.modules['pvporcupine'] = MagicMock()

from RealtimeSTT import AudioToTextRecorder

def process_text(text):
    print(f"Transcribed: {text}")
    # Later this is where you'll send text to the OLED display

def main():
    print("Loading model...")
    recorder = AudioToTextRecorder(
        model="base",              # tiny, base, small
        realtime_model_type="base",
        language="en",
        compute_type="int8",       # faster on Pi
        silero_sensitivity=0.6,    # VAD sensitivity 0-1
        webrtc_sensitivity=1,      # 0-3, noise filtering
        post_speech_silence_duration=0.4,
        min_length_of_recording=0.5,   # don't discard short utterances
        on_realtime_transcription_update=process_text,  # called as you speak
        enable_realtime_transcription=True,
        input_device_index=1,
        wakeword_backend="none",
    )

    print("Listening... (Press Ctrl+C to stop)\n")

    try:
        while True:
            # This blocks until a full sentence is finalized
            # but process_text fires in real-time as you speak
            recorder.text(process_text)
    except KeyboardInterrupt:
        print("\nStopped.")
        recorder.stop()

if __name__ == "__main__":
    main()
