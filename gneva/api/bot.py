"""Recall.ai bot management endpoints."""

import uuid
import httpx
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.db import get_db
from gneva.models.user import User
from gneva.models.meeting import Meeting
from gneva.auth import get_current_user
from gneva.config import get_settings

router = APIRouter(prefix="/api/bot", tags=["bot"])
settings = get_settings()


class BotJoinRequest(BaseModel):
    meeting_url: str
    platform: str = "zoom"
    meeting_title: str | None = None


class BotJoinResponse(BaseModel):
    meeting_id: str
    recall_bot_id: str
    status: str


@router.post("/join", response_model=BotJoinResponse)
async def join_meeting(
    req: BotJoinRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not settings.recall_api_key:
        raise HTTPException(status_code=503, detail="Recall.ai not configured")

    # Create meeting record
    meeting = Meeting(
        org_id=user.org_id,
        platform=req.platform,
        title=req.meeting_title,
        status="joining",
    )
    db.add(meeting)
    await db.flush()

    # Call Recall.ai to create bot
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{settings.recall_api_url}/bot",
                headers={"Authorization": f"Token {settings.recall_api_key}"},
                json={
                    "meeting_url": req.meeting_url,
                    "bot_name": "Gneva",
                    "transcription_options": {"provider": "default"},
                    "real_time_transcription": {"destination_url": f"{settings.recall_webhook_url}/api/internal/recall-webhook"},
                },
                timeout=30,
            )
            resp.raise_for_status()
            bot_data = resp.json()
        except httpx.HTTPError as e:
            meeting.status = "failed"
            raise HTTPException(status_code=502, detail=f"Recall.ai error: {e}")

    meeting.recall_bot_id = bot_data.get("id")
    meeting.status = "joining"

    return BotJoinResponse(
        meeting_id=str(meeting.id),
        recall_bot_id=meeting.recall_bot_id,
        status="joining",
    )


@router.post("/leave")
async def leave_meeting(
    meeting_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    meeting = (await db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.org_id == user.org_id)
    )).scalar_one_or_none()
    if not meeting or not meeting.recall_bot_id:
        raise HTTPException(status_code=404, detail="Meeting/bot not found")

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{settings.recall_api_url}/bot/{meeting.recall_bot_id}/leave_call",
                headers={"Authorization": f"Token {settings.recall_api_key}"},
                timeout=15,
            )
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Recall.ai error: {e}")

    meeting.status = "ended"
    return {"status": "ok"}


@router.get("/status/{recall_bot_id}")
async def bot_status(
    recall_bot_id: str,
    user: User = Depends(get_current_user),
):
    if not settings.recall_api_key:
        raise HTTPException(status_code=503, detail="Recall.ai not configured")

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{settings.recall_api_url}/bot/{recall_bot_id}",
                headers={"Authorization": f"Token {settings.recall_api_key}"},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Recall.ai error: {e}")
