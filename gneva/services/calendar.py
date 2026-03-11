"""Calendar sync service — Google Calendar and Microsoft Graph integration."""

import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.models.calendar import CalendarEvent
from gneva.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
MS_GRAPH_API = "https://graph.microsoft.com/v1.0"

MEETING_URL_PATTERNS = [
    (r"https?://[\w.-]*zoom\.us/j/\d+[^\s\"'<>]*", "zoom"),
    (r"https?://meet\.google\.com/[\w-]+", "meet"),
    (r"https?://teams\.microsoft\.com/l/meetup-join/[^\s\"'<>]+", "teams"),
    (r"https?://[\w.-]*webex\.com/[\w./]+", "webex"),
]


def detect_platform(url: str) -> str | None:
    """Detect meeting platform from a URL."""
    if not url:
        return None
    domain = urlparse(url).netloc.lower()
    if "zoom" in domain:
        return "zoom"
    if "meet.google.com" in domain:
        return "meet"
    if "teams.microsoft.com" in domain:
        return "teams"
    if "webex" in domain:
        return "webex"
    return None


def extract_meeting_url(event: dict) -> str | None:
    """Extract meeting URL from event body, location, or conference data.

    Checks (in order):
    1. Google Calendar conferenceData.entryPoints
    2. Microsoft Graph onlineMeeting.joinUrl
    3. Location field
    4. Description/body text via regex
    """
    # Google conferenceData
    conf = event.get("conferenceData", {})
    for ep in conf.get("entryPoints", []):
        if ep.get("entryPointType") == "video":
            return ep.get("uri")

    # MS Graph onlineMeeting
    online = event.get("onlineMeeting")
    if online and online.get("joinUrl"):
        return online["joinUrl"]

    # Check location
    location = event.get("location", "") or ""
    if isinstance(location, dict):
        location = location.get("displayName", "")
    for pattern, _ in MEETING_URL_PATTERNS:
        match = re.search(pattern, location)
        if match:
            return match.group(0)

    # Check description/body
    description = event.get("description", "") or ""
    if isinstance(description, dict):
        description = description.get("content", "")
    body = event.get("body", {})
    if isinstance(body, dict):
        description = description or body.get("content", "")
    for pattern, _ in MEETING_URL_PATTERNS:
        match = re.search(pattern, description)
        if match:
            return match.group(0)

    return None


async def sync_google_calendar(
    db: AsyncSession, user_id: str, org_id: str, credentials_json: dict
) -> list[CalendarEvent]:
    """Fetch events from Google Calendar for the next 7 days and upsert them."""
    access_token = credentials_json.get("access_token", "")
    now = datetime.utcnow()
    time_min = now.isoformat()
    time_max = (now + timedelta(days=7)).isoformat()

    events = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        page_token = None
        while True:
            params = {
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 250,
            }
            if page_token:
                params["pageToken"] = page_token

            resp = await client.get(
                f"{GOOGLE_CALENDAR_API}/calendars/primary/events",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code != 200:
                logger.error(f"Google Calendar API error {resp.status_code}: {resp.text}")
                break

            data = resp.json()
            for item in data.get("items", []):
                if item.get("status") == "cancelled":
                    continue
                start = item.get("start", {})
                end = item.get("end", {})
                start_dt = _parse_google_dt(start)
                end_dt = _parse_google_dt(end)
                if not start_dt or not end_dt:
                    continue

                meeting_url = extract_meeting_url(item)
                platform = detect_platform(meeting_url) if meeting_url else None
                attendees = [
                    {
                        "email": a.get("email", ""),
                        "name": a.get("displayName", ""),
                        "response_status": a.get("responseStatus", "needsAction"),
                    }
                    for a in item.get("attendees", [])
                ]

                cal_event = await _upsert_calendar_event(
                    db,
                    org_id=org_id,
                    user_id=user_id,
                    provider="google",
                    provider_event_id=item["id"],
                    title=item.get("summary", "Untitled"),
                    description=item.get("description"),
                    meeting_url=meeting_url,
                    platform=platform,
                    start_time=start_dt,
                    end_time=end_dt,
                    attendees_json=attendees,
                )
                events.append(cal_event)

            page_token = data.get("nextPageToken")
            if not page_token:
                break

    await db.flush()
    return events


async def sync_outlook_calendar(
    db: AsyncSession, user_id: str, org_id: str, credentials_json: dict
) -> list[CalendarEvent]:
    """Fetch events from Outlook/Microsoft Graph for the next 7 days and upsert them."""
    access_token = credentials_json.get("access_token", "")
    now = datetime.utcnow()
    time_min = now.isoformat()
    time_max = (now + timedelta(days=7)).isoformat()

    events = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{MS_GRAPH_API}/me/calendarview"
        params = {"startDateTime": time_min, "endDateTime": time_max, "$top": 250}

        while url:
            resp = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code != 200:
                logger.error(f"MS Graph API error {resp.status_code}: {resp.text}")
                break

            data = resp.json()
            for item in data.get("value", []):
                if item.get("isCancelled"):
                    continue
                start_dt = _parse_ms_dt(item.get("start", {}))
                end_dt = _parse_ms_dt(item.get("end", {}))
                if not start_dt or not end_dt:
                    continue

                meeting_url = extract_meeting_url(item)
                platform = detect_platform(meeting_url) if meeting_url else None
                attendees = [
                    {
                        "email": a.get("emailAddress", {}).get("address", ""),
                        "name": a.get("emailAddress", {}).get("name", ""),
                        "response_status": a.get("status", {}).get("response", "none"),
                    }
                    for a in item.get("attendees", [])
                ]

                cal_event = await _upsert_calendar_event(
                    db,
                    org_id=org_id,
                    user_id=user_id,
                    provider="outlook",
                    provider_event_id=item["id"],
                    title=item.get("subject", "Untitled"),
                    description=item.get("bodyPreview"),
                    meeting_url=meeting_url,
                    platform=platform,
                    start_time=start_dt,
                    end_time=end_dt,
                    attendees_json=attendees,
                )
                events.append(cal_event)

            # Handle pagination — validate URL to prevent SSRF
            next_url = data.get("@odata.nextLink")
            if next_url and not next_url.startswith("https://graph.microsoft.com"):
                logger.warning("Suspicious pagination URL: %s", next_url)
                break
            url = next_url
            params = {}  # nextLink already has params

    await db.flush()
    return events


async def get_upcoming_meetings(
    db: AsyncSession, org_id: str, hours: int = 24
) -> list[CalendarEvent]:
    """Query upcoming calendar events that have meeting URLs."""
    cutoff = datetime.utcnow() + timedelta(hours=hours)
    now = datetime.utcnow()

    result = await db.execute(
        select(CalendarEvent).where(
            and_(
                CalendarEvent.org_id == org_id,
                CalendarEvent.start_time >= now,
                CalendarEvent.start_time <= cutoff,
                CalendarEvent.meeting_url.isnot(None),
            )
        ).order_by(CalendarEvent.start_time)
    )
    return list(result.scalars().all())


async def auto_schedule_joins(db: AsyncSession, org_id: str) -> list[dict]:
    """For events with auto_join=True starting in the next 5 minutes, schedule bot joins.

    Returns a list of {event_id, meeting_url, platform, start_time} for the bot manager.
    """
    now = datetime.utcnow()
    join_window = now + timedelta(minutes=5)

    result = await db.execute(
        select(CalendarEvent).where(
            and_(
                CalendarEvent.org_id == org_id,
                CalendarEvent.auto_join.is_(True),
                CalendarEvent.meeting_url.isnot(None),
                CalendarEvent.meeting_id.is_(None),  # not already joined
                CalendarEvent.start_time >= now - timedelta(minutes=1),
                CalendarEvent.start_time <= join_window,
            )
        ).order_by(CalendarEvent.start_time)
    )
    events = result.scalars().all()

    scheduled = []
    for event in events:
        scheduled.append({
            "event_id": str(event.id),
            "meeting_url": event.meeting_url,
            "platform": event.platform or detect_platform(event.meeting_url),
            "title": event.title,
            "start_time": event.start_time.isoformat(),
        })

    return scheduled


async def _upsert_calendar_event(
    db: AsyncSession, *, org_id: str, user_id: str, provider: str,
    provider_event_id: str, title: str, description: str | None,
    meeting_url: str | None, platform: str | None,
    start_time: datetime, end_time: datetime, attendees_json: list,
) -> CalendarEvent:
    """Insert or update a calendar event by provider + provider_event_id."""
    result = await db.execute(
        select(CalendarEvent).where(
            and_(
                CalendarEvent.org_id == org_id,
                CalendarEvent.provider == provider,
                CalendarEvent.provider_event_id == provider_event_id,
            )
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.title = title
        existing.description = description
        existing.meeting_url = meeting_url
        existing.platform = platform
        existing.start_time = start_time
        existing.end_time = end_time
        existing.attendees_json = attendees_json
        existing.synced_at = datetime.utcnow()
        return existing

    event = CalendarEvent(
        org_id=org_id,
        user_id=user_id,
        provider=provider,
        provider_event_id=provider_event_id,
        title=title,
        description=description,
        meeting_url=meeting_url,
        platform=platform,
        start_time=start_time,
        end_time=end_time,
        attendees_json=attendees_json,
    )
    db.add(event)
    return event


def _parse_google_dt(dt_obj: dict) -> datetime | None:
    """Parse Google Calendar dateTime or date field."""
    dt_str = dt_obj.get("dateTime")
    if dt_str:
        dt = datetime.fromisoformat(dt_str)
        return dt.replace(tzinfo=None)
    date_str = dt_obj.get("date")
    if date_str:
        dt = datetime.fromisoformat(date_str + "T00:00:00+00:00")
        return dt.replace(tzinfo=None)
    return None


def _parse_ms_dt(dt_obj: dict) -> datetime | None:
    """Parse Microsoft Graph start/end datetime object."""
    dt_str = dt_obj.get("dateTime")
    tz_name = dt_obj.get("timeZone", "UTC")
    if not dt_str:
        return None
    # MS Graph returns datetime without timezone info but with timeZone field
    # For simplicity, treat as UTC (production would use pytz)
    dt = datetime.fromisoformat(dt_str.rstrip("Z"))
    return dt.replace(tzinfo=None)
