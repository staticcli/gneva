"""Analytics API routes — org stats, speaker breakdown, patterns, and trends."""

import uuid
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.db import get_db
from gneva.models.user import User
from gneva.models.calendar import MeetingPattern, SpeakerAnalytics
from gneva.models.meeting import Meeting, MeetingSummary
from gneva.auth import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class SpeakerBreakdownResponse(BaseModel):
    speaker_label: str
    user_id: str | None
    talk_time_sec: float
    word_count: int
    interruption_count: int
    question_count: int
    sentiment_avg: float | None
    talk_percentage: float


class PatternResponse(BaseModel):
    id: str
    pattern_type: str
    title: str
    description: str
    confidence: float
    severity: str
    status: str
    evidence: list | dict
    detected_at: datetime


@router.get("/overview")
async def get_overview(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get org-level analytics overview."""
    from gneva.services.analytics import get_org_analytics

    stats = await get_org_analytics(db, str(user.org_id), days=days)
    return stats


@router.get("/meetings/{meeting_id}/speakers", response_model=list[SpeakerBreakdownResponse])
async def get_speaker_breakdown(
    meeting_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get speaker breakdown for a specific meeting."""
    # Verify meeting belongs to org
    meeting_result = await db.execute(
        select(Meeting).where(
            and_(Meeting.id == meeting_id, Meeting.org_id == user.org_id)
        )
    )
    if not meeting_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Meeting not found")

    result = await db.execute(
        select(SpeakerAnalytics).where(SpeakerAnalytics.meeting_id == meeting_id)
    )
    analytics = list(result.scalars().all())

    if not analytics:
        # Try computing on the fly
        from gneva.services.analytics import compute_speaker_analytics
        analytics = await compute_speaker_analytics(db, str(meeting_id))

    total_talk = sum(a.talk_time_sec for a in analytics) or 1.0

    return [
        SpeakerBreakdownResponse(
            speaker_label=a.speaker_label,
            user_id=str(a.user_id) if a.user_id else None,
            talk_time_sec=round(a.talk_time_sec, 1),
            word_count=a.word_count,
            interruption_count=a.interruption_count,
            question_count=a.question_count,
            sentiment_avg=round(a.sentiment_avg, 2) if a.sentiment_avg is not None else None,
            talk_percentage=round(a.talk_time_sec / total_talk * 100, 1),
        )
        for a in analytics
    ]


@router.get("/patterns")
async def get_patterns(
    status: str = Query("active", description="Filter by status: active, dismissed, resolved"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get detected meeting patterns for the org."""
    base = (
        select(MeetingPattern)
        .where(
            and_(
                MeetingPattern.org_id == user.org_id,
                MeetingPattern.status == status,
            )
        )
    )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    result = await db.execute(
        base.order_by(MeetingPattern.detected_at.desc()).offset(offset).limit(limit)
    )
    patterns = result.scalars().all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "patterns": [
            PatternResponse(
                id=str(p.id),
                pattern_type=p.pattern_type,
                title=p.title,
                description=p.description,
                confidence=round(p.confidence, 2),
                severity=p.severity,
                status=p.status,
                evidence=p.evidence_json if isinstance(p.evidence_json, (dict, list)) else [],
                detected_at=p.detected_at,
            )
            for p in patterns
        ],
    }


@router.post("/patterns/{pattern_id}/dismiss")
async def dismiss_pattern(
    pattern_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dismiss a detected pattern."""
    result = await db.execute(
        select(MeetingPattern).where(
            and_(
                MeetingPattern.id == pattern_id,
                MeetingPattern.org_id == user.org_id,
            )
        )
    )
    pattern = result.scalar_one_or_none()
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    if pattern.status != "active":
        raise HTTPException(status_code=400, detail=f"Pattern is already {pattern.status}")

    pattern.status = "dismissed"
    pattern.dismissed_at = datetime.utcnow()
    await db.flush()

    return {"status": "dismissed", "id": str(pattern_id)}


@router.get("/trends")
async def get_trends(
    days: int = Query(30, ge=7, le=365),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get meeting frequency, sentiment, and topic trends over time.

    Returns weekly aggregated data points for charts.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Meeting frequency by week
    meetings_result = await db.execute(
        select(Meeting.created_at, Meeting.duration_sec, Meeting.participant_count)
        .where(
            and_(
                Meeting.org_id == user.org_id,
                Meeting.status == "complete",
                Meeting.created_at >= cutoff,
            )
        )
        .order_by(Meeting.created_at)
    )
    meetings_raw = meetings_result.all()

    # Sentiment by week
    sentiment_result = await db.execute(
        select(MeetingSummary.created_at, MeetingSummary.sentiment)
        .join(Meeting, Meeting.id == MeetingSummary.meeting_id)
        .where(
            and_(
                Meeting.org_id == user.org_id,
                Meeting.status == "complete",
                Meeting.created_at >= cutoff,
            )
        )
        .order_by(MeetingSummary.created_at)
    )
    sentiments_raw = sentiment_result.all()

    # Aggregate into weekly buckets
    weekly_meetings = {}
    for created_at, duration_sec, participant_count in meetings_raw:
        week_start = created_at.strftime("%Y-W%W")
        if week_start not in weekly_meetings:
            weekly_meetings[week_start] = {
                "week": week_start,
                "meeting_count": 0,
                "total_duration_sec": 0,
                "avg_participants": [],
            }
        bucket = weekly_meetings[week_start]
        bucket["meeting_count"] += 1
        bucket["total_duration_sec"] += duration_sec or 0
        if participant_count:
            bucket["avg_participants"].append(participant_count)

    meeting_trends = []
    for week, data in sorted(weekly_meetings.items()):
        participants = data["avg_participants"]
        meeting_trends.append({
            "week": data["week"],
            "meeting_count": data["meeting_count"],
            "total_hours": round(data["total_duration_sec"] / 3600, 1),
            "avg_participants": round(sum(participants) / len(participants), 1) if participants else 0,
        })

    # Sentiment trends
    sentiment_map = {"positive": 1.0, "neutral": 0.0, "negative": -1.0, "frustrated": -0.8, "excited": 0.8}
    weekly_sentiments = {}
    for created_at, sentiment in sentiments_raw:
        week_start = created_at.strftime("%Y-W%W")
        if week_start not in weekly_sentiments:
            weekly_sentiments[week_start] = []
        if sentiment and sentiment.lower() in sentiment_map:
            weekly_sentiments[week_start].append(sentiment_map[sentiment.lower()])

    sentiment_trends = []
    for week in sorted(weekly_sentiments.keys()):
        values = weekly_sentiments[week]
        if values:
            sentiment_trends.append({
                "week": week,
                "avg_sentiment": round(sum(values) / len(values), 2),
                "count": len(values),
            })

    return {
        "period_days": days,
        "meeting_trends": meeting_trends,
        "sentiment_trends": sentiment_trends,
    }
