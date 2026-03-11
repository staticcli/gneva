"""Notification API routes — list, read, and manage notifications."""

import uuid
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.db import get_db
from gneva.models.user import User
from gneva.auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationResponse(BaseModel):
    id: str
    type: str
    title: str
    body: str
    meeting_id: str | None
    action_item_id: str | None
    channel: str
    read: bool
    sent_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    total: int
    unread_count: int


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List notifications for the current user, unread first."""
    from gneva.services.notifications import get_all_notifications, get_unread_count

    notifications, total = await get_all_notifications(
        db, str(user.id), offset=offset, limit=limit
    )
    unread = await get_unread_count(db, str(user.id))

    return NotificationListResponse(
        notifications=[
            NotificationResponse(
                id=str(n.id),
                type=n.type,
                title=n.title,
                body=n.body,
                meeting_id=str(n.meeting_id) if n.meeting_id else None,
                action_item_id=str(n.action_item_id) if n.action_item_id else None,
                channel=n.channel,
                read=n.read,
                sent_at=n.sent_at,
                created_at=n.created_at,
            )
            for n in notifications
        ],
        total=total,
        unread_count=unread,
    )


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a single notification as read."""
    from gneva.services.notifications import mark_read

    success = await mark_read(db, str(notification_id), str(user.id))
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "read", "id": str(notification_id)}


@router.post("/read-all")
async def mark_all_notifications_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    from gneva.services.notifications import mark_all_read

    count = await mark_all_read(db, str(user.id))
    return {"status": "ok", "marked_read": count}


@router.get("/unread-count")
async def get_unread_notification_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the count of unread notifications (for badge display)."""
    from gneva.services.notifications import get_unread_count

    count = await get_unread_count(db, str(user.id))
    return {"unread_count": count}
