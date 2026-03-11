"""Team dynamics endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.db import get_db
from gneva.models.user import User
from gneva.models.meeting import Meeting, Transcript, TranscriptSegment
from gneva.auth import get_current_user

router = APIRouter(prefix="/api/dynamics", tags=["dynamics"])


@router.get("/speakers")
async def speaker_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Join TranscriptSegment -> Transcript -> Meeting, filter by org
    stmt = (
        select(
            TranscriptSegment.speaker_label,
            func.count(TranscriptSegment.id).label("total_segments"),
            func.sum(func.length(TranscriptSegment.text)).label("total_chars"),
            func.count(func.distinct(Meeting.id)).label("meetings_participated"),
        )
        .join(Transcript, TranscriptSegment.transcript_id == Transcript.id)
        .join(Meeting, Transcript.meeting_id == Meeting.id)
        .where(Meeting.org_id == user.org_id)
        .where(TranscriptSegment.speaker_label != None)
        .group_by(TranscriptSegment.speaker_label)
        .order_by(func.sum(func.length(TranscriptSegment.text)).desc())
    )

    rows = (await db.execute(stmt)).all()

    speakers = []
    for row in rows:
        total_segments = row.total_segments or 0
        total_chars = row.total_chars or 0
        # Approximate words from chars (avg ~5 chars per word)
        total_words = total_chars // 5
        avg_words = total_words // max(total_segments, 1)
        speakers.append({
            "speaker": row.speaker_label,
            "total_segments": total_segments,
            "total_words": total_words,
            "meetings_participated": row.meetings_participated or 0,
            "avg_words_per_segment": avg_words,
        })

    return {"speakers": speakers}


@router.get("/meeting/{meeting_id}/balance")
async def meeting_balance(
    meeting_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meeting = (await db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.org_id == user.org_id)
    )).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    stmt = (
        select(
            TranscriptSegment.speaker_label,
            func.count(TranscriptSegment.id).label("segment_count"),
            func.sum(func.length(TranscriptSegment.text)).label("total_chars"),
        )
        .join(Transcript, TranscriptSegment.transcript_id == Transcript.id)
        .where(Transcript.meeting_id == meeting_id)
        .where(TranscriptSegment.speaker_label != None)
        .group_by(TranscriptSegment.speaker_label)
    )

    rows = (await db.execute(stmt)).all()

    total_all_chars = sum((r.total_chars or 0) for r in rows)
    speakers = []
    for row in rows:
        chars = row.total_chars or 0
        word_count = chars // 5
        pct = round(chars / max(total_all_chars, 1) * 100, 1)
        speakers.append({
            "speaker": row.speaker_label,
            "segment_count": row.segment_count or 0,
            "word_count": word_count,
            "percentage_of_talk_time": pct,
        })

    speakers.sort(key=lambda s: s["word_count"], reverse=True)

    most_talkative = speakers[0]["speaker"] if speakers else None
    quietest = speakers[-1]["speaker"] if speakers else None

    return {
        "meeting_id": str(meeting_id),
        "title": meeting.title,
        "speakers": speakers,
        "most_talkative": most_talkative,
        "quietest": quietest,
    }
