"""Recall.ai webhook handler — receives bot status updates and transcript chunks."""

import asyncio
import logging
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from gneva.config import get_settings
from gneva.db import async_session_factory
from gneva.models.meeting import Meeting
from gneva.pipeline.runner import process_meeting

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhook"])
settings = get_settings()

_background_tasks: set = set()


def _create_background_task(coro):
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(lambda t: (_background_tasks.discard(t), t.exception() if not t.cancelled() and t.exception() else None))
    return task


@router.post("/api/internal/recall-webhook")
async def recall_webhook(request: Request):
    """Handle Recall.ai webhook events."""
    # Authenticate webhook via shared secret
    if not settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Webhook secret not configured")
    incoming_secret = request.headers.get("X-Webhook-Secret", "")
    if incoming_secret != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    data = await request.json()
    event = data.get("event", "")
    bot_id = data.get("bot_id", "")

    logger.info(f"Recall webhook: event={event} bot_id={bot_id}")

    async with async_session_factory() as db:
        meeting = (await db.execute(
            select(Meeting).where(Meeting.bot_id == bot_id)
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
                _create_background_task(process_meeting(str(meeting.id)))

        elif event == "recording.complete":
            # Audio is ready for download
            meeting.raw_audio_path = data.get("data", {}).get("recording_url", "")
            meeting.status = "processing"
            _create_background_task(process_meeting(str(meeting.id)))

        await db.commit()

    return {"status": "ok"}
