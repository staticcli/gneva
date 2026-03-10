"""Recall.ai webhook handler — receives bot status updates and transcript chunks."""

import logging
from fastapi import APIRouter, Request
from sqlalchemy import select

from gneva.db import async_session
from gneva.models.meeting import Meeting

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhook"])


@router.post("/api/internal/recall-webhook")
async def recall_webhook(request: Request):
    """Handle Recall.ai webhook events."""
    data = await request.json()
    event = data.get("event", "")
    bot_id = data.get("bot_id", "")

    logger.info(f"Recall webhook: event={event} bot_id={bot_id}")

    async with async_session() as db:
        meeting = (await db.execute(
            select(Meeting).where(Meeting.recall_bot_id == bot_id)
        )).scalar_one_or_none()

        if not meeting:
            logger.warning(f"No meeting found for bot {bot_id}")
            return {"status": "ignored"}

        if event == "bot.status_change":
            status = data.get("data", {}).get("status", "")
            if status == "in_call":
                meeting.status = "active"
                meeting.participant_count = data.get("data", {}).get("participant_count")
            elif status == "done":
                meeting.status = "processing"
                # Trigger the processing pipeline
                from gneva.tasks import process_meeting
                process_meeting.delay(str(meeting.id))

        elif event == "recording.complete":
            # Audio is ready for download
            meeting.raw_audio_path = data.get("data", {}).get("recording_url", "")
            meeting.status = "processing"
            from gneva.tasks import process_meeting
            process_meeting.delay(str(meeting.id))

        await db.commit()

    return {"status": "ok"}
