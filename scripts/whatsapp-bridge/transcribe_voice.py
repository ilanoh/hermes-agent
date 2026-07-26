"""Prints the transcript of one audio file: transcribe_voice.py <model folder> <audio file>.

Called by voice_transcriber.js. The language is detected per file (a mashgiah
answers in Hebrew or English), and silence is skipped so nothing is invented
over it.
"""

import sys

from faster_whisper import WhisperModel


def main() -> None:
    model_dir, audio_path = sys.argv[1], sys.argv[2]
    model = WhisperModel(model_dir, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(audio_path, vad_filter=True, beam_size=5)
    print(" ".join(segment.text.strip() for segment in segments).strip())


if __name__ == "__main__":
    main()
