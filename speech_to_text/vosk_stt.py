import vosk
import pyaudio
import json

# Path to your downloaded model folder
MODEL_PATH = "../text-controller-mvp/src/app/vosk-model-small-en-us-0.15"

def main():
    # Load the Vosk model
    print("Loading model...")
    model = vosk.Model(MODEL_PATH)

    # Set up PyAudio
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=8000
    )

    # Set up the recognizer
    recognizer = vosk.KaldiRecognizer(model, 16000)

    print("Listening... (Press Ctrl+C to stop)\n")

    try:
        while True:
            # Read audio chunk from microphone
            data = stream.read(4000, exception_on_overflow=False)

            # Feed audio to recognizer
            if recognizer.AcceptWaveform(data):
                # Full sentence detected
                result = json.loads(recognizer.Result())
                text = result.get("text", "")
                if text:
                    print(f"Recognized: {text}")
            else:
                # Partial result (word by word as you speak)
                partial = json.loads(recognizer.PartialResult())
                partial_text = partial.get("partial", "")
                if partial_text:
                    print(f"Partial: {partial_text}", end="\r")

    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    main()
