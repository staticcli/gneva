"""Audio/video file upload endpoint."""

import logging
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.auth import get_current_user
from gneva.config import get_settings
from gneva.db import get_db
from gneva.models.meeting import Meeting
from gneva.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()

_background_tasks: set = set()


def _create_background_task(coro):
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(lambda t: (_background_tasks.discard(t), t.exception() if not t.cancelled() and t.exception() else None))
    return task

router = APIRouter(prefix="/api/upload", tags=["upload"])

ALLOWED_EXTENSIONS = {"wav", "mp3", "m4a", "ogg", "webm", "mp4"}
ALLOWED_CONTENT_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/ogg",
    "audio/webm",
    "video/mp4",
    "video/webm",
}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500 MB


def _get_extension(filename: str) -> str:
    """Extract and validate file extension."""
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


@router.post("/audio")
async def upload_audio(
    file: UploadFile = File(...),
    title: str = Form(None),
    platform: str = Form("upload"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload an audio or video file for processing.

    Accepts WAV, MP3, M4A, OGG, WEBM, and MP4 files up to 500 MB.
    The file is streamed to disk and a processing pipeline is triggered.
    """
    # Validate extension
    ext = _get_extension(file.filename or "")
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '.{ext}' not allowed. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Validate content type
    content_type = (file.content_type or "").lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Content type '{content_type}' not allowed.",
        )

    # Ensure storage directory exists
    storage_dir = Path(settings.audio_storage_path)
    storage_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    file_id = uuid.uuid4()
    dest_path = storage_dir / f"{file_id}.{ext}"

    # Stream file to disk with size check
    total_size = 0
    try:
        async with aiofiles.open(dest_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB chunks
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum size of {MAX_FILE_SIZE // (1024 * 1024)} MB.",
                    )
                await out.write(chunk)
    except HTTPException:
        # Clean up partial file on size limit
        dest_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save file.")

    if total_size == 0:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Create meeting record
    meeting = Meeting(
        org_id=user.org_id,
        platform=platform,
        title=title or file.filename,
        status="processing",
        raw_audio_path=str(dest_path),
    )
    db.add(meeting)
    await db.flush()
    meeting_id = meeting.id

    # Trigger processing pipeline
    import asyncio
    try:
        from gneva.pipeline.runner import process_meeting
        _create_background_task(process_meeting(str(meeting_id)))
    except Exception as e:
        logger.warning(f"Failed to start processing for meeting {meeting_id}: {e}")

    logger.info(f"Uploaded audio file for meeting {meeting_id}: {dest_path} ({total_size} bytes)")

    return {
        "meeting_id": str(meeting_id),
        "status": "processing",
        "file_size": total_size,
        "filename": file.filename,
    }
