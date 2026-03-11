"""Meeting ROI score endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.db import get_db
from gneva.models.user import User
from gneva.models.meeting import Meeting
from gneva.models.entity import Decision, ActionItem, EntityMention
from gneva.auth import get_current_user

router = APIRouter(prefix="/api/roi", tags=["roi"])


def _grade(score: float) -> str:
    if score >= 80:
        return "A"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    if score >= 20:
        return "D"
    return "F"


@router.get("/meetings/{meeting_id}")
async def meeting_roi(
    meeting_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meeting = (await db.execute(
        select(Meeting).where(Meeting.id == meeting_id, Meeting.org_id == user.org_id)
    )).scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    decisions_made = (await db.execute(
        select(func.count()).select_from(Decision).where(Decision.meeting_id == meeting_id)
    )).scalar() or 0

    actions_assigned = (await db.execute(
        select(func.count()).select_from(ActionItem).where(ActionItem.meeting_id == meeting_id)
    )).scalar() or 0

    key_topics = (await db.execute(
        select(func.count(func.distinct(EntityMention.entity_id)))
        .where(EntityMention.meeting_id == meeting_id)
    )).scalar() or 0

    duration_min = (meeting.duration_sec or 0) / 60.0
    participant_count = meeting.participant_count or 0

    score = (decisions_made * 30 + actions_assigned * 20 + key_topics * 5) / max(duration_min, 1) * 10
    score = round(score, 1)

    return {
        "meeting_id": str(meeting_id),
        "title": meeting.title,
        "decisions_made": decisions_made,
        "actions_assigned": actions_assigned,
        "key_topics": key_topics,
        "duration_min": round(duration_min, 1),
        "participant_count": participant_count,
        "score": score,
        "grade": _grade(score),
    }


@router.get("/overview")
async def roi_overview(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    meetings = (await db.execute(
        select(Meeting)
        .where(Meeting.org_id == user.org_id)
        .order_by(Meeting.created_at.desc())
        .limit(20)
    )).scalars().all()

    results = []
    total_score = 0.0

    for m in meetings:
        mid = m.id
        decisions_made = (await db.execute(
            select(func.count()).select_from(Decision).where(Decision.meeting_id == mid)
        )).scalar() or 0

        actions_assigned = (await db.execute(
            select(func.count()).select_from(ActionItem).where(ActionItem.meeting_id == mid)
        )).scalar() or 0

        key_topics = (await db.execute(
            select(func.count(func.distinct(EntityMention.entity_id)))
            .where(EntityMention.meeting_id == mid)
        )).scalar() or 0

        duration_min = (m.duration_sec or 0) / 60.0
        score = (decisions_made * 30 + actions_assigned * 20 + key_topics * 5) / max(duration_min, 1) * 10
        score = round(score, 1)
        total_score += score

        results.append({
            "meeting_id": str(mid),
            "title": m.title,
            "decisions_made": decisions_made,
            "actions_assigned": actions_assigned,
            "key_topics": key_topics,
            "duration_min": round(duration_min, 1),
            "participant_count": m.participant_count or 0,
            "score": score,
            "grade": _grade(score),
            "created_at": m.created_at.isoformat(),
        })

    avg_score = round(total_score / len(results), 1) if results else 0.0

    return {
        "average_score": avg_score,
        "average_grade": _grade(avg_score),
        "meeting_count": len(results),
        "meetings": results,
    }
