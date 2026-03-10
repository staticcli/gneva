"""Celery task definitions for the processing pipeline."""

import logging
from celery import Celery

from gneva.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

celery_app = Celery("gneva", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_routes={
        "gneva.tasks.transcribe_audio": {"queue": "gpu"},
        "gneva.tasks.diarize_audio": {"queue": "cpu_heavy"},
        "gneva.tasks.extract_entities": {"queue": "io"},
        "gneva.tasks.embed_segments": {"queue": "cpu_heavy"},
        "gneva.tasks.generate_summary": {"queue": "io"},
    },
)


@celery_app.task(name="gneva.tasks.process_meeting")
def process_meeting(meeting_id: str):
    """Orchestrate the full processing pipeline for a completed meeting."""
    logger.info(f"Starting pipeline for meeting {meeting_id}")

    # Chain: download → transcribe → diarize → embed → extract → summarize
    from celery import chain
    pipeline = chain(
        download_audio.s(meeting_id),
        transcribe_audio.s(),
        diarize_audio.s(),
        embed_segments.s(),
        extract_entities.s(),
        generate_summary.s(),
    )
    pipeline.apply_async()


@celery_app.task(name="gneva.tasks.download_audio")
def download_audio(meeting_id: str):
    """Download audio from Recall.ai CDN to local/S3 storage."""
    logger.info(f"Downloading audio for meeting {meeting_id}")
    # TODO: Implement Recall.ai audio download
    return {"meeting_id": meeting_id, "audio_path": f"/tmp/gneva/audio/{meeting_id}.wav"}


@celery_app.task(name="gneva.tasks.transcribe_audio")
def transcribe_audio(prev_result: dict):
    """Transcribe audio using faster-whisper."""
    meeting_id = prev_result["meeting_id"]
    audio_path = prev_result["audio_path"]
    logger.info(f"Transcribing {audio_path}")
    # TODO: Implement faster-whisper transcription
    return {"meeting_id": meeting_id, "audio_path": audio_path}


@celery_app.task(name="gneva.tasks.diarize_audio")
def diarize_audio(prev_result: dict):
    """Run speaker diarization using pyannote."""
    meeting_id = prev_result["meeting_id"]
    audio_path = prev_result["audio_path"]
    logger.info(f"Diarizing {audio_path}")
    # TODO: Implement pyannote diarization
    return {"meeting_id": meeting_id, "audio_path": audio_path}


@celery_app.task(name="gneva.tasks.embed_segments")
def embed_segments(prev_result: dict):
    """Embed transcript segments using nomic-embed-text."""
    meeting_id = prev_result["meeting_id"]
    logger.info(f"Embedding segments for meeting {meeting_id}")
    # TODO: Implement nomic embedding
    return {"meeting_id": meeting_id}


@celery_app.task(name="gneva.tasks.extract_entities")
def extract_entities(prev_result: dict):
    """Extract entities from transcript using Claude Haiku."""
    meeting_id = prev_result["meeting_id"]
    logger.info(f"Extracting entities for meeting {meeting_id}")
    # TODO: Implement Claude entity extraction
    return {"meeting_id": meeting_id}


@celery_app.task(name="gneva.tasks.generate_summary")
def generate_summary(prev_result: dict):
    """Generate meeting summary using Claude Sonnet."""
    meeting_id = prev_result["meeting_id"]
    logger.info(f"Generating summary for meeting {meeting_id}")
    # TODO: Implement Claude summary generation
    return {"meeting_id": meeting_id, "status": "complete"}
