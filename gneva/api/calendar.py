"""Calendar API routes — connect, sync, and manage calendar events."""

import logging
import uuid
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.db import get_db
from gneva.models.user import User
from gneva.models.calendar import CalendarEvent
from gneva.auth import get_current_user
from gneva.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/calendar", tags=["calendar"])
settings = get_settings()


class CalendarConnectRequest(BaseModel):
    provider: str  # google or outlook
    credentials: dict  # OAuth tokens


class CalendarEventResponse(BaseModel):
    id: str
    provider: str
    title: str
    description: str | None
    meeting_url: str | None
    platform: str | None
    start_time: datetime
    end_time: datetime
    attendees: list[dict]
    auto_join: bool
    meeting_id: str | None
    synced_at: datetime


class CalendarEventToggle(BaseModel):
    auto_join: bool


# In-memory credential store (production would use encrypted DB column or vault)
_calendar_credentials: dict[str, dict] = {}


@router.post("/connect")
async def connect_calendar(
    req: CalendarConnectRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store calendar credentials and trigger initial sync."""
    if req.provider not in ("google", "outlook"):
        raise HTTPException(status_code=400, detail="Provider must be 'google' or 'outlook'")

    if req.provider == "google" and not settings.google_calendar_enabled:
        raise HTTPException(status_code=400, detail="Google Calendar integration is not enabled")
    if req.provider == "outlook" and not settings.outlook_calendar_enabled:
        raise HTTPException(status_code=400, detail="Outlook Calendar integration is not enabled")

    # Store credentials keyed by user_id + provider
    cred_key = f"{user.id}:{req.provider}"
    _calendar_credentials[cred_key] = req.credentials

    # Trigger sync
    from gneva.services.calendar import sync_google_calendar, sync_outlook_calendar

    try:
        if req.provider == "google":
            events = await sync_google_calendar(
                db, str(user.id), str(user.org_id), req.credentials
            )
        else:
            events = await sync_outlook_calendar(
                db, str(user.id), str(user.org_id), req.credentials
            )
        return {"status": "connected", "provider": req.provider, "events_synced": len(events)}
    except Exception as e:
        logger.error("Calendar sync failed: %s", e)
        raise HTTPException(status_code=502, detail="Calendar sync failed")


@router.post("/sync")
async def sync_calendar(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual calendar sync for all connected providers."""
    from gneva.services.calendar import sync_google_calendar, sync_outlook_calendar

    total_synced = 0
    errors = []

    for provider in ("google", "outlook"):
        cred_key = f"{user.id}:{provider}"
        creds = _calendar_credentials.get(cred_key)
        if not creds:
            continue

        try:
            if provider == "google":
                events = await sync_google_calendar(
                    db, str(user.id), str(user.org_id), creds
                )
            else:
                events = await sync_outlook_calendar(
                    db, str(user.id), str(user.org_id), creds
                )
            total_synced += len(events)
        except Exception as e:
            logger.error("Calendar sync failed for %s: %s", provider, e)
            errors.append({"provider": provider, "error": "sync failed"})

    if not total_synced and not errors:
        raise HTTPException(status_code=400, detail="No calendars connected. Use POST /api/calendar/connect first.")

    return {"events_synced": total_synced, "errors": errors}


@router.get("/events", response_model=list[CalendarEventResponse])
async def list_events(
    days: int = Query(7, ge=1, le=30),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List upcoming calendar events for the user's org."""
    from gneva.services.calendar import get_upcoming_meetings
    from datetime import timedelta, timezone as tz

    events = await get_upcoming_meetings(db, str(user.org_id), hours=days * 24)

    return [
        CalendarEventResponse(
            id=str(e.id),
            provider=e.provider,
            title=e.title,
            description=e.description,
            meeting_url=e.meeting_url,
            platform=e.platform,
            start_time=e.start_time,
            end_time=e.end_time,
            attendees=e.attendees_json if isinstance(e.attendees_json, list) else [],
            auto_join=e.auto_join,
            meeting_id=str(e.meeting_id) if e.meeting_id else None,
            synced_at=e.synced_at,
        )
        for e in events
    ]


@router.patch("/events/{event_id}")
async def toggle_auto_join(
    event_id: uuid.UUID,
    body: CalendarEventToggle,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle auto_join for a calendar event."""
    result = await db.execute(
        select(CalendarEvent).where(
            and_(
                CalendarEvent.id == event_id,
                CalendarEvent.org_id == user.org_id,
            )
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Calendar event not found")

    if body.auto_join and not event.meeting_url:
        raise HTTPException(status_code=400, detail="Cannot auto-join: no meeting URL detected for this event")

    event.auto_join = body.auto_join
    await db.flush()

    return {
        "id": str(event.id),
        "auto_join": event.auto_join,
        "title": event.title,
    }


@router.delete("/disconnect")
async def disconnect_calendar(
    provider: str = Query(..., description="google or outlook"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove calendar connection and delete synced events."""
    if provider not in ("google", "outlook"):
        raise HTTPException(status_code=400, detail="Provider must be 'google' or 'outlook'")

    cred_key = f"{user.id}:{provider}"
    removed = _calendar_credentials.pop(cred_key, None)

    # Delete calendar events from this provider for this user
    result = await db.execute(
        select(CalendarEvent).where(
            and_(
                CalendarEvent.user_id == user.id,
                CalendarEvent.provider == provider,
                CalendarEvent.meeting_id.is_(None),  # don't delete events linked to meetings
            )
        )
    )
    events = result.scalars().all()
    deleted_count = 0
    for event in events:
        await db.delete(event)
        deleted_count += 1

    await db.flush()

    return {
        "status": "disconnected" if removed else "not_connected",
        "provider": provider,
        "events_deleted": deleted_count,
    }
