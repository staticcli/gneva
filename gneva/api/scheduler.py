"""Scheduler / PM API routes — follow-ups, status reports, meeting suggestions, dashboard."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.auth import get_current_user
from gneva.db import get_db
from gneva.models.entity import ActionItem
from gneva.models.meeting import Meeting
from gneva.models.user import User
from gneva.services.scheduler import Scheduler

router = APIRouter(prefix="/api/pm", tags=["pm"])

_scheduler: Scheduler | None = None


def set_scheduler(s: Scheduler) -> None:
    """Set the shared scheduler instance (called from lifespan)."""
    global _scheduler
    _scheduler = s


def _get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler


class FollowUpUpdate(BaseModel):
    status: Literal["open", "in_progress", "done"] | None = None
    due_date: str | None = None
    priority: Literal["high", "medium", "low"] | None = None


# ------------------------------------------------------------------
# Follow-ups
# ------------------------------------------------------------------
@router.get("/follow-ups")
async def list_follow_ups(
    status: str = Query("all", pattern="^(all|open|in_progress|overdue|done)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List follow-up action items, optionally filtered by status."""
    today = datetime.utcnow().date()

    query = select(ActionItem).where(ActionItem.org_id == user.org_id)

    if status == "overdue":
        query = query.where(
            ActionItem.status.in_(["open", "in_progress"]),
            ActionItem.due_date < today,
        )
    elif status == "done":
        query = query.where(ActionItem.status == "done")
    elif status != "all":
        query = query.where(ActionItem.status == status)
    else:
        query = query.where(ActionItem.status.in_(["open", "in_progress"]))

    query = query.order_by(ActionItem.due_date.asc().nullslast(), ActionItem.created_at.desc())

    items = (await db.execute(query)).scalars().all()

    return {
        "follow_ups": [
            {
                "id": str(a.id),
                "description": a.description,
                "assignee_id": str(a.assignee_id) if a.assignee_id else None,
                "due_date": str(a.due_date) if a.due_date else None,
                "priority": a.priority,
                "status": a.status,
                "overdue": bool(a.due_date and a.due_date < today and a.status in ("open", "in_progress")),
                "meeting_id": str(a.meeting_id),
                "created_at": a.created_at.isoformat(),
            }
            for a in items
        ],
        "total": len(items),
    }


@router.patch("/follow-ups/{follow_up_id}")
async def update_follow_up(
    follow_up_id: uuid.UUID,
    update: FollowUpUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a follow-up's status, due date, or priority."""
    item = (await db.execute(
        select(ActionItem)
        .where(ActionItem.id == follow_up_id, ActionItem.org_id == user.org_id)
    )).scalar_one_or_none()

    if not item:
        raise HTTPException(status_code=404, detail="Follow-up not found")

    if update.status:
        item.status = update.status
        if update.status == "done":
            item.completed_at = datetime.utcnow()

    if update.due_date:
        from datetime import date as date_type
        item.due_date = date_type.fromisoformat(update.due_date)

    if update.priority:
        item.priority = update.priority

    return {"status": "updated", "id": str(item.id)}


# ------------------------------------------------------------------
# Status report
# ------------------------------------------------------------------
@router.get("/status-report")
async def get_status_report(
    user: User = Depends(get_current_user),
):
    """Generate or retrieve the weekly status report."""
    scheduler = _get_scheduler()
    report = await scheduler.generate_status_report(user.org_id)
    return report


# ------------------------------------------------------------------
# Meeting suggestions
# ------------------------------------------------------------------
@router.post("/suggest-meetings")
async def suggest_meetings(
    user: User = Depends(get_current_user),
):
    """Get AI-powered meeting suggestions based on patterns and gaps."""
    scheduler = _get_scheduler()
    suggestions = await scheduler.suggest_meetings(user.org_id)
    return {"suggestions": suggestions}


# ------------------------------------------------------------------
# PM dashboard
# ------------------------------------------------------------------
@router.get("/dashboard")
async def pm_dashboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """PM overview: overdue items, upcoming meetings, patterns, stats."""
    today = datetime.utcnow().date()
    now = datetime.utcnow()

    # Overdue action items
    overdue_count = (await db.execute(
        select(func.count()).select_from(ActionItem)
        .where(
            ActionItem.org_id == user.org_id,
            ActionItem.status.in_(["open", "in_progress"]),
            ActionItem.due_date < today,
        )
    )).scalar() or 0

    # Due today
    due_today_count = (await db.execute(
        select(func.count()).select_from(ActionItem)
        .where(
            ActionItem.org_id == user.org_id,
            ActionItem.status.in_(["open", "in_progress"]),
            ActionItem.due_date == today,
        )
    )).scalar() or 0

    # Total open items
    open_count = (await db.execute(
        select(func.count()).select_from(ActionItem)
        .where(
            ActionItem.org_id == user.org_id,
            ActionItem.status.in_(["open", "in_progress"]),
        )
    )).scalar() or 0

    # Upcoming meetings (next 24h)
    upcoming = (await db.execute(
        select(Meeting)
        .where(
            Meeting.org_id == user.org_id,
            Meeting.status == "scheduled",
            Meeting.scheduled_at >= now,
            Meeting.scheduled_at <= now + timedelta(hours=24),
        )
        .order_by(Meeting.scheduled_at.asc())
    )).scalars().all()

    # Recent meetings (last 7 days)
    recent_count = (await db.execute(
        select(func.count()).select_from(Meeting)
        .where(
            Meeting.org_id == user.org_id,
            Meeting.created_at >= now - timedelta(days=7),
        )
    )).scalar() or 0

    # Top overdue items
    overdue_items = (await db.execute(
        select(ActionItem)
        .where(
            ActionItem.org_id == user.org_id,
            ActionItem.status.in_(["open", "in_progress"]),
            ActionItem.due_date < today,
        )
        .order_by(ActionItem.due_date.asc())
        .limit(5)
    )).scalars().all()

    return {
        "stats": {
            "overdue": overdue_count,
            "due_today": due_today_count,
            "open_total": open_count,
            "meetings_this_week": recent_count,
        },
        "upcoming_meetings": [
            {
                "id": str(m.id),
                "title": m.title or "Untitled",
                "scheduled_at": m.scheduled_at.isoformat() if m.scheduled_at else None,
                "platform": m.platform,
            }
            for m in upcoming
        ],
        "overdue_items": [
            {
                "id": str(a.id),
                "description": a.description,
                "due_date": str(a.due_date) if a.due_date else None,
                "priority": a.priority,
                "days_overdue": (today - a.due_date).days if a.due_date else 0,
            }
            for a in overdue_items
        ],
    }
