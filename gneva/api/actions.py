"""Action item management endpoints."""

import uuid
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.db import get_db
from gneva.models.user import User
from gneva.models.entity import ActionItem
from gneva.auth import get_current_user

router = APIRouter(prefix="/api/actions", tags=["actions"])


class ActionItemUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None


@router.get("")
async def list_action_items(
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(ActionItem).where(ActionItem.org_id == user.org_id)
    if status:
        query = query.where(ActionItem.status == status)
    else:
        query = query.where(ActionItem.status.in_(["open", "in_progress"]))
    query = query.order_by(ActionItem.created_at.desc())

    items = (await db.execute(query)).scalars().all()

    return {
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


@router.patch("/{action_id}")
async def update_action_item(
    action_id: uuid.UUID,
    update: ActionItemUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    item = (await db.execute(
        select(ActionItem).where(ActionItem.id == action_id, ActionItem.org_id == user.org_id)
    )).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Action item not found")

    if update.status:
        item.status = update.status
        if update.status == "done":
            from datetime import datetime, timezone
            item.completed_at = datetime.now(timezone.utc)
    if update.priority:
        item.priority = update.priority

    return {"status": "updated"}


@router.get("/by-person/{user_id}")
async def action_items_by_person(
    user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(ActionItem)
        .where(ActionItem.org_id == user.org_id, ActionItem.assignee_id == user_id)
        .where(ActionItem.status.in_(["open", "in_progress"]))
        .order_by(ActionItem.created_at.desc())
    )).scalars().all()

    return {
        "action_items": [
            {
                "id": str(a.id),
                "description": a.description,
                "due_date": str(a.due_date) if a.due_date else None,
                "priority": a.priority,
                "status": a.status,
                "meeting_id": str(a.meeting_id),
            }
            for a in items
        ],
    }
