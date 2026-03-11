"""Follow-up enforcement endpoints."""

import uuid
from datetime import datetime, timedelta, date

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.db import get_db
from gneva.models.user import User
from gneva.models.entity import ActionItem
from gneva.auth import get_current_user

router = APIRouter(prefix="/api/followups", tags=["followups"])


@router.get("/overdue")
async def overdue_followups(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.utcnow() - timedelta(days=7)
    items = (await db.execute(
        select(ActionItem)
        .where(
            ActionItem.org_id == user.org_id,
            ActionItem.status == "open",
            ActionItem.created_at < cutoff,
        )
        .order_by(ActionItem.created_at.asc())
    )).scalars().all()

    # Group by assignee_id
    grouped: dict[str, list] = {}
    for a in items:
        days_overdue = (datetime.utcnow() - a.created_at).days - 7
        assignee_key = str(a.assignee_id) if a.assignee_id else "unassigned"
        item_data = {
            "id": str(a.id),
            "description": a.description,
            "assignee_id": str(a.assignee_id) if a.assignee_id else None,
            "due_date": str(a.due_date) if a.due_date else None,
            "priority": a.priority,
            "meeting_id": str(a.meeting_id),
            "created_at": a.created_at.isoformat(),
            "days_overdue": days_overdue,
        }
        grouped.setdefault(assignee_key, []).append(item_data)

    return {
        "total_overdue": len(items),
        "by_assignee": grouped,
    }


@router.get("/upcoming")
async def upcoming_followups(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    three_days = today + timedelta(days=3)

    items = (await db.execute(
        select(ActionItem)
        .where(
            ActionItem.org_id == user.org_id,
            ActionItem.status.in_(["open", "in_progress"]),
            ActionItem.due_date != None,
            ActionItem.due_date >= today,
            ActionItem.due_date <= three_days,
        )
        .order_by(ActionItem.due_date.asc())
    )).scalars().all()

    return {
        "total_upcoming": len(items),
        "action_items": [
            {
                "id": str(a.id),
                "description": a.description,
                "assignee_id": str(a.assignee_id) if a.assignee_id else None,
                "due_date": str(a.due_date) if a.due_date else None,
                "priority": a.priority,
                "status": a.status,
                "meeting_id": str(a.meeting_id),
                "created_at": a.created_at.isoformat(),
            }
            for a in items
        ],
    }


class NudgeResponse(BaseModel):
    status: str


@router.post("/{action_id}/nudge")
async def nudge_action(
    action_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = (await db.execute(
        select(ActionItem).where(ActionItem.id == action_id, ActionItem.org_id == user.org_id)
    )).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")

    # Mark as nudged via the entity metadata pattern used in the codebase
    # ActionItem doesn't have metadata_json, so we use status prefix approach
    # Store nudge info in description suffix to keep it simple without schema changes
    from gneva.models.entity import Entity
    entity = (await db.execute(
        select(Entity).where(Entity.id == item.entity_id)
    )).scalar_one_or_none()

    if entity:
        meta = entity.metadata_json or {}
        nudges = meta.get("nudges", [])
        nudges.append({
            "action_id": str(action_id),
            "nudged_by": str(user.id),
            "nudged_at": datetime.utcnow().isoformat(),
        })
        meta["nudges"] = nudges
        entity.metadata_json = meta

    return {"status": "nudged", "action_id": str(action_id)}
