from RealtimeSTT import AudioToTextRecorder

def process_text(text):
    print(f"Transcribed: {text}")
    # Later this is where you'll send text to the OLED display

def main():
    print("Loading model...")
    recorder = AudioToTextRecorder(
        model="base",              # tiny, base, small
        language="en",
        compute_type="int8",       # faster on Pi
        silero_sensitivity=0.4,    # VAD sensitivity 0-1
        webrtc_sensitivity=3,      # 0-3, noise filtering
        on_realtime_transcription_update=process_text,  # called as you speak
        enable_realtime_transcription=True,
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