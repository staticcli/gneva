"""Speaker diarization using pyannote."""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SpeakerSegment:
    speaker: str  # "SPEAKER_00", "SPEAKER_01", etc.
    start_ms: int
    end_ms: int


def diarize(audio_path: str, num_speakers: int | None = None) -> list[SpeakerSegment]:
    """Run speaker diarization on audio file.

    Args:
        audio_path: Path to audio file
        num_speakers: Expected number of speakers (None for auto-detect)

    Returns:
        List of speaker segments with timestamps
    """
    from pyannote.audio import Pipeline

    logger.info(f"Running diarization on {audio_path}")

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=True,  # requires HF_TOKEN env var
    )

    kwargs = {}
    if num_speakers:
        kwargs["num_speakers"] = min(num_speakers, 10)  # cap at 10

    diarization = pipeline(audio_path, **kwargs)

    segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append(SpeakerSegment(
            speaker=speaker,
            start_ms=int(turn.start * 1000),
            end_ms=int(turn.end * 1000),
        ))

    logger.info(f"Found {len(set(s.speaker for s in segments))} speakers, {len(segments)} segments")
    return segments


def assign_speakers(word_segments: list, speaker_segments: list[SpeakerSegment]) -> list[dict]:
    """Merge word-level transcription with speaker diarization.

    Assigns each word to a speaker based on timestamp overlap.
    Groups consecutive words by the same speaker into utterance segments.
    """
    # Build speaker timeline for fast lookup
    utterances = []
    current_speaker = None
    current_words = []
    current_start = 0

    for word in word_segments:
        word_mid = (word.start_ms + word.end_ms) // 2

        # Find which speaker owns this timestamp
        speaker = "Unknown"
        for seg in speaker_segments:
            if seg.start_ms <= word_mid <= seg.end_ms:
                speaker = seg.speaker
                break

        if speaker != current_speaker and current_words:
            utterances.append({
                "speaker_label": current_speaker,
                "start_ms": current_start,
                "end_ms": current_words[-1].end_ms,
                "text": " ".join(w.word for w in current_words),
                "confidence": sum(w.confidence for w in current_words) / len(current_words),
            })
            current_words = []

        if not current_words:
            current_start = word.start_ms
        current_speaker = speaker
        current_words.append(word)

    # Final segment
    if current_words:
        utterances.append({
            "speaker_label": current_speaker,
            "start_ms": current_start,
            "end_ms": current_words[-1].end_ms,
            "text": " ".join(w.word for w in current_words),
            "confidence": sum(w.confidence for w in current_words) / len(current_words),
        })

    return utterances
