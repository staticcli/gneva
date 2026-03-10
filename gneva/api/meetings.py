"""Meeting CRUD and detail endpoints."""

import uuid
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gneva.db import get_db
from gneva.models.user import User
from gneva.models.meeting import Meeting, Transcript, TranscriptSegment, MeetingSummary
from gneva.models.entity import ActionItem, Decision, EntityMention, Entity
from gneva.auth import get_current_user

router = APIRouter(prefix="/api/meetings", tags=["meetings"])


class MeetingCreate(BaseModel):
    platform: str
    title: str | None = None
    meeting_url: str | None = None
    scheduled_at: datetime | None = None


class MeetingResponse(BaseModel):
    id: str
    platform: str
    title: str | None
    status: str
    scheduled_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None
    duration_sec: int | None
    participant_count: int | None
    created_at: datetime


class MeetingListResponse(BaseModel):
    meetings: list[MeetingResponse]
    total: int


@router.get("", response_model=MeetingListResponse)
async def list_meetings(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Meeting).where(Meeting.org_id == user.org_id).order_by(Meeting.created_at.desc())
    if status:
        query = query.where(Meeting.status == status)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    result = await db.execute(query.offset(offset).limit(limit))
    meetings = result.scalars().all()

    return MeetingListResponse(
        meetings=[
            MeetingResponse(
                id=str(m.id), platform=m.platform, title=m.title, status=m.status,
                scheduled_at=m.scheduled_at, started_at=m.started_at, ended_at=m.ended_at,
                duration_sec=m.duration_sec, participant_count=m.participant_count,
                created_at=m.created_at,
            )
            for m in meetings
        ],
        total=total,
    )


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.org_id == user.org_id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return MeetingResponse(
        id=str(meeting.id), platform=meeting.platform, title=meeting.title,
        status=meeting.status, scheduled_at=meeting.scheduled_at,
        started_at=meeting.started_at, ended_at=meeting.ended_at,
        duration_sec=meeting.duration_sec, participant_count=meeting.participant_count,
        created_at=meeting.created_at,
    )


@router.get("/{meeting_id}/transcript")
async def get_transcript(
    meeting_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify meeting belongs to org
    meeting = (await db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.org_id == user.org_id)
    )).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Get latest transcript version
    transcript = (await db.execute(
        select(Transcript)
        .where(Transcript.meeting_id == meeting_id)
        .order_by(Transcript.version.desc())
    )).scalar_one_or_none()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not available")

    # Get segments
    segments = (await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.transcript_id == transcript.id)
        .order_by(TranscriptSegment.start_ms)
    )).scalars().all()

    return {
        "transcript_id": str(transcript.id),
        "version": transcript.version,
        "full_text": transcript.full_text,
        "word_count": transcript.word_count,
        "segments": [
            {
                "id": str(s.id),
                "speaker_label": s.speaker_label,
                "start_ms": s.start_ms,
                "end_ms": s.end_ms,
                "text": s.text,
                "confidence": s.confidence,
            }
            for s in segments
        ],
    }


@router.get("/{meeting_id}/summary")
async def get_summary(
    meeting_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meeting = (await db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.org_id == user.org_id)
    )).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    summary = (await db.execute(
        select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_id)
    )).scalar_one_or_none()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not available yet")

    return {
        "meeting_id": str(meeting_id),
        "tldr": summary.tldr,
        "key_decisions": summary.key_decisions,
        "topics_covered": summary.topics_covered,
        "sentiment": summary.sentiment,
        "follow_up_needed": summary.follow_up_needed,
    }


@router.get("/{meeting_id}/action-items")
async def get_action_items(
    meeting_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meeting = (await db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.org_id == user.org_id)
    )).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    items = (await db.execute(
        select(ActionItem).where(ActionItem.meeting_id == meeting_id)
    )).scalars().all()

    return {
        "meeting_id": str(meeting_id),
        "action_items": [
            {
                "id": str(a.id),
                "description": a.description,
                "assignee_id": str(a.assignee_id) if a.assignee_id else None,
                "due_date": str(a.due_date) if a.due_date else None,
                "priority": a.priority,
                "status": a.status,
            }
            for a in items
        ],
    }


@router.get("/{meeting_id}/decisions")
async def get_decisions(
    meeting_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meeting = (await db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.org_id == user.org_id)
    )).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    decisions = (await db.execute(
        select(Decision).where(Decision.meeting_id == meeting_id)
    )).scalars().all()

    return {
        "meeting_id": str(meeting_id),
        "decisions": [
            {
                "id": str(d.id),
                "statement": d.statement,
                "rationale": d.rationale,
                "status": d.status,
                "confidence": d.confidence,
            }
            for d in decisions
        ],
    }
