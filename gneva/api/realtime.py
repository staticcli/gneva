"""Real-time API routes — WebSocket streaming, live context, segment push."""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from gneva.auth import get_current_user, decode_token
from gneva.db import get_db, async_session_factory
from gneva.models.meeting import Meeting
from gneva.models.user import User
from gneva.services.realtime import RealtimeEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/realtime", tags=["realtime"])

_engine: RealtimeEngine | None = None


def _get_engine() -> RealtimeEngine:
    global _engine
    if _engine is None:
        _engine = RealtimeEngine()
    return _engine


class SegmentRequest(BaseModel):
    meeting_id: str
    text: str
    speaker: str


# ------------------------------------------------------------------
# WebSocket: live transcript streaming
# ------------------------------------------------------------------
@router.websocket("/stream/{meeting_id}")
async def realtime_stream(websocket: WebSocket, meeting_id: str):
    """WebSocket for bidirectional live transcript streaming.

    Client sends: {"text": "...", "speaker": "...", "token": "..."}
    Server sends: {"type": "ack"} or {"type": "gneva_response", "text": "..."}
    """
    await websocket.accept()

    engine = _get_engine()
    mid = uuid.UUID(meeting_id)
    org_id: uuid.UUID | None = None

    # ---- Authentication: first message MUST contain a valid token ----
    try:
        raw = await websocket.receive_text()
    except WebSocketDisconnect:
        return

    try:
        first_msg = json.loads(raw)
    except json.JSONDecodeError:
        await websocket.send_json({"type": "error", "message": "Invalid JSON"})
        await websocket.close(code=4001)
        return

    token = first_msg.get("token", "")
    if not token:
        await websocket.send_json({"type": "error", "message": "First message must contain a token"})
        await websocket.close(code=4001)
        return

    try:
        payload = decode_token(token)
        org_id = uuid.UUID(payload["org_id"])
    except Exception:
        await websocket.send_json({"type": "error", "message": "Invalid token"})
        await websocket.close(code=4001)
        return

    # Verify the meeting belongs to the authenticated user's org
    async with async_session_factory() as db:
        meeting = (await db.execute(
            select(Meeting).where(
                Meeting.id == mid,
                Meeting.org_id == org_id,
            )
        )).scalar_one_or_none()
    if not meeting:
        await websocket.send_json({"type": "error", "message": "Meeting not found or access denied"})
        await websocket.close(code=4003)
        return

    await websocket.send_json({"type": "auth", "status": "ok"})

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            text = data.get("text", "").strip()
            speaker = data.get("speaker", "Unknown")

            if not text:
                await websocket.send_json({"type": "ack", "status": "empty"})
                continue

            # Process segment
            await engine.process_live_segment(mid, text, speaker, org_id=org_id)
            await websocket.send_json({"type": "ack", "status": "ok"})

            # Check if Gneva should respond
            should_speak, response = await engine.should_gneva_speak(mid)
            if should_speak and response:
                await websocket.send_json({
                    "type": "gneva_response",
                    "text": response,
                    "speaker": "Gneva",
                })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for meeting %s", meeting_id)
        engine.end_meeting(mid)
    except Exception:
        logger.exception("WebSocket error for meeting %s", meeting_id)
        engine.end_meeting(mid)


# ------------------------------------------------------------------
# REST: get current live context
# ------------------------------------------------------------------
@router.get("/context/{meeting_id}")
async def get_live_context(
    meeting_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current live meeting context (topics, speakers, key points)."""
    mid = uuid.UUID(meeting_id)

    # Verify the meeting belongs to the user's org
    meeting = (await db.execute(
        select(Meeting).where(Meeting.id == mid, Meeting.org_id == user.org_id)
    )).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=403, detail="Meeting not found or access denied")

    engine = _get_engine()
    context = engine.get_live_context(mid)
    return context


# ------------------------------------------------------------------
# REST: push a live transcript segment
# ------------------------------------------------------------------
@router.post("/segment")
async def push_segment(
    req: SegmentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Push a live transcript segment (alternative to WebSocket)."""
    mid = uuid.UUID(req.meeting_id)

    # Verify the meeting belongs to the user's org
    meeting = (await db.execute(
        select(Meeting).where(Meeting.id == mid, Meeting.org_id == user.org_id)
    )).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=403, detail="Meeting not found or access denied")

    engine = _get_engine()
    await engine.process_live_segment(mid, req.text, req.speaker, org_id=user.org_id)

    should_speak, response = await engine.should_gneva_speak(mid)

    result = {"status": "ok", "segment_processed": True}
    if should_speak and response:
        result["gneva_response"] = response
    return result
