"""Transcription using faster-whisper."""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WordSegment:
    word: str
    start_ms: int
    end_ms: int
    confidence: float


@dataclass
class TranscriptionResult:
    segments: list[WordSegment]
    full_text: str
    language: str
    word_count: int


def transcribe(audio_path: str, model_size: str = "large-v3", device: str = "cuda") -> TranscriptionResult:
    """Transcribe audio file using faster-whisper.

    Args:
        audio_path: Path to audio file (WAV, MP3, etc.)
        model_size: Whisper model size (tiny, base, small, medium, large-v3)
        device: Device to run on (cuda or cpu)

    Returns:
        TranscriptionResult with word-level segments
    """
    from faster_whisper import WhisperModel

    logger.info(f"Loading whisper model {model_size} on {device}")
    model = WhisperModel(model_size, device=device, compute_type="float16" if device == "cuda" else "int8")

    segments_iter, info = model.transcribe(
        audio_path,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    word_segments = []
    full_text_parts = []

    for segment in segments_iter:
        full_text_parts.append(segment.text.strip())
        if segment.words:
            for word in segment.words:
                word_segments.append(WordSegment(
                    word=word.word.strip(),
                    start_ms=int(word.start * 1000),
                    end_ms=int(word.end * 1000),
                    confidence=word.probability,
                ))

    full_text = " ".join(full_text_parts)

    logger.info(f"Transcribed {len(word_segments)} words, language={info.language}")

    return TranscriptionResult(
        segments=word_segments,
        full_text=full_text,
        language=info.language,
        word_count=len(word_segments),
    )
