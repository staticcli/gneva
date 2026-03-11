"""Meeting bot endpoints — join/leave/status via native Playwright bot."""

import asyncio
import uuid
import logging
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.db import get_db
from gneva.models.user import User
from gneva.models.meeting import Meeting
from gneva.auth import get_current_user
from gneva.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/bot", tags=["bot"])
settings = get_settings()

_background_tasks: set = set()


def _create_background_task(coro):
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(lambda t: (_background_tasks.discard(t), t.exception() if not t.cancelled() and t.exception() else None))
    return task

# BotManager singleton — initialized at app startup
_bot_manager = None


def get_bot_manager():
    if _bot_manager is None:
        raise HTTPException(status_code=503, detail="Bot manager not initialized")
    return _bot_manager


def set_bot_manager(manager):
    global _bot_manager
    _bot_manager = manager


class BotJoinRequest(BaseModel):
    meeting_url: str
    platform: str = "auto"  # "auto", "zoom", "google_meet", "teams"
    meeting_title: str | None = None
    bot_name: str | None = None  # override default name


class BotJoinResponse(BaseModel):
    meeting_id: str
    bot_id: str
    status: str
    platform: str


class BotLeaveRequest(BaseModel):
    meeting_id: str | None = None
    bot_id: str | None = None


@router.post("/join", response_model=BotJoinResponse)
async def join_meeting(
    req: BotJoinRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send Gneva to join a meeting."""
    manager = get_bot_manager()

    # Auto-detect platform from URL
    from gneva.bot.platforms import detect_platform
    try:
        platform = detect_platform(req.meeting_url) if req.platform == "auto" else req.platform
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create meeting record
    meeting = Meeting(
        org_id=user.org_id,
        platform=platform,
        title=req.meeting_title,
        status="joining",
    )
    db.add(meeting)
    await db.flush()

    meeting_id_str = str(meeting.id)

    # Define completion callback to update meeting status
    async def on_bot_complete(bot_id, meeting_id, audio_path, success):
        from gneva.db import async_session_factory
        async with async_session_factory() as session:
            result = await session.execute(
                select(Meeting).where(Meeting.id == uuid.UUID(meeting_id))
            )
            m = result.scalar_one_or_none()
            if m:
                m.status = "processing" if success else "failed"
                m.raw_audio_path = audio_path
                await session.commit()
                if success:
                    from gneva.pipeline.runner import process_meeting
                    _create_background_task(process_meeting(meeting_id))

    # Launch the bot
    try:
        bot_id = await manager.join(
            meeting_url=req.meeting_url,
            meeting_id=meeting_id_str,
            bot_name=req.bot_name or settings.bot_name,
            on_complete=on_bot_complete,
        )
    except RuntimeError as e:
        meeting.status = "failed"
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        meeting.status = "failed"
        logger.error("Bot launch failed: %s", e)
        raise HTTPException(status_code=500, detail="Bot launch failed")

    meeting.bot_id = bot_id

    return BotJoinResponse(
        meeting_id=meeting_id_str,
        bot_id=bot_id,
        status="joining",
        platform=platform,
    )


@router.post("/leave")
async def leave_meeting(
    req: BotLeaveRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tell Gneva to leave a meeting."""
    manager = get_bot_manager()

    bot_id = req.bot_id

    # Look up bot_id from meeting_id if not provided
    if not bot_id and req.meeting_id:
        result = await db.execute(
            select(Meeting).where(
                Meeting.id == uuid.UUID(req.meeting_id),
                Meeting.org_id == user.org_id,
            )
        )
        meeting = result.scalar_one_or_none()
        if not meeting or not meeting.bot_id:
            raise HTTPException(status_code=404, detail="Meeting/bot not found")
        bot_id = meeting.bot_id

    if not bot_id:
        raise HTTPException(status_code=400, detail="Provide meeting_id or bot_id")

    try:
        await manager.leave(bot_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found")

    return {"status": "leaving", "bot_id": bot_id}


@router.get("/status/{bot_id}")
async def bot_status(
    bot_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the status of a bot."""
    # Verify the bot's meeting belongs to the user's org
    result = await db.execute(
        select(Meeting).where(Meeting.bot_id == bot_id, Meeting.org_id == user.org_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Bot not found")

    manager = get_bot_manager()
    try:
        return manager.status(bot_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found")


@router.get("/active")
async def list_active_bots(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active and recent bots."""
    # Get bot_ids that belong to the user's org
    result = await db.execute(
        select(Meeting.bot_id).where(
            Meeting.org_id == user.org_id,
            Meeting.bot_id.isnot(None),
        )
    )
    org_bot_ids = {row[0] for row in result.all()}

    manager = get_bot_manager()
    all_bots = manager.list_bots()
    # Filter to only bots belonging to this org
    org_bots = [b for b in all_bots if b.get("bot_id") in org_bot_ids]
    return {"bots": org_bots}
