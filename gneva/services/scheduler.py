"""Background scheduler — autonomous PM actions: reminders, digests, follow-ups."""

import asyncio
import logging
import uuid
from datetime import datetime, date, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.config import get_settings
from gneva.db import async_session_factory
from gneva.models.calendar import Notification
from gneva.models.entity import ActionItem, Decision, Entity
from gneva.models.meeting import Meeting, MeetingSummary
from gneva.models.user import Organization, User

logger = logging.getLogger(__name__)
settings = get_settings()


class Scheduler:
    """Async background scheduler that runs proactive PM tasks every 60s."""

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._tick_interval = 60  # seconds

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Scheduler started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._tick()
            except Exception:
                logger.exception("Scheduler tick failed")
            await asyncio.sleep(self._tick_interval)

    # ------------------------------------------------------------------
    # Main tick — runs every 60 seconds
    # ------------------------------------------------------------------
    async def _tick(self) -> None:
        now = datetime.utcnow()
        today = now.date()

        async with async_session_factory() as db:
            result = await db.execute(select(Organization))
            org_ids = [org.id for org in result.scalars().all()]

        for org_id in org_ids:
            # 1. Check overdue / due-today action items
            try:
                await self.check_action_items(org_id)
            except Exception:
                logger.exception("Action item check failed for org %s", org_id)

            # 2. Weekly digest (configurable day/hour, default Friday 5 PM)
            if (
                now.weekday() == settings.weekly_digest_day
                and now.hour == settings.weekly_digest_hour
                and now.minute == 0
            ):
                try:
                    await self._send_weekly_digests(org_id)
                except Exception:
                    logger.exception("Weekly digest failed for org %s", org_id)

            # 3. Daily pattern detection (run at midnight UTC)
            if now.hour == 0 and now.minute == 0:
                try:
                    await self._detect_patterns(org_id)
                except Exception:
                    logger.exception("Pattern detection failed for org %s", org_id)

        # 4. Calendar auto-join (check for meetings starting in ~2 min)
        try:
            await self._check_calendar_autojoin()
        except Exception:
            logger.exception("Calendar auto-join check failed")

    # ------------------------------------------------------------------
    # Action item checks
    # ------------------------------------------------------------------
    async def check_action_items(self, org_id: uuid.UUID) -> list[dict]:
        """Find overdue and due-today items, send notifications."""
        today = datetime.utcnow().date()
        results = []

        async with async_session_factory() as db:
            # Overdue items
            overdue = (await db.execute(
                select(ActionItem)
                .where(
                    ActionItem.org_id == org_id,
                    ActionItem.status.in_(["open", "in_progress"]),
                    ActionItem.due_date < today,
                )
            )).scalars().all()

            # Due today
            due_today = (await db.execute(
                select(ActionItem)
                .where(
                    ActionItem.org_id == org_id,
                    ActionItem.status.in_(["open", "in_progress"]),
                    ActionItem.due_date == today,
                )
            )).scalars().all()

        for item in overdue:
            results.append({
                "action_item_id": str(item.id),
                "description": item.description,
                "due_date": str(item.due_date),
                "status": "overdue",
                "assignee_id": str(item.assignee_id) if item.assignee_id else None,
            })
            # Dedup: skip if already notified today for this action item
            if not await self._already_notified_today(item.id, today):
                await self._notify_action_item(item, overdue=True)

        for item in due_today:
            results.append({
                "action_item_id": str(item.id),
                "description": item.description,
                "due_date": str(item.due_date),
                "status": "due_today",
                "assignee_id": str(item.assignee_id) if item.assignee_id else None,
            })
            # Dedup: skip if already notified today for this action item
            if not await self._already_notified_today(item.id, today):
                await self._notify_action_item(item, overdue=False)

        return results

    async def _already_notified_today(self, action_item_id: uuid.UUID, today: date) -> bool:
        """Check if a reminder was already sent today for this action item."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(func.count()).where(
                    and_(
                        Notification.action_item_id == action_item_id,
                        Notification.type == "action_item_due",
                        func.date(Notification.created_at) == today,
                    )
                )
            )
            return (result.scalar() or 0) > 0

    async def _notify_action_item(self, item: ActionItem, overdue: bool) -> None:
        """Send email and/or Slack reminder for an action item."""
        if not item.assignee_id:
            return
        async with async_session_factory() as db:
            user = (await db.execute(
                select(User).where(User.id == item.assignee_id)
            )).scalar_one_or_none()

        if not user:
            return

        # Email reminder
        try:
            from gneva.services.email import send_action_reminder
            await send_action_reminder(user.email, item)
        except Exception:
            logger.debug("Email reminder failed for %s", user.email)

    # ------------------------------------------------------------------
    # Weekly digest
    # ------------------------------------------------------------------
    async def _send_weekly_digests(self, org_id: uuid.UUID) -> None:
        async with async_session_factory() as db:
            result = await db.execute(
                select(User).where(User.org_id == org_id)
            )
            user_emails = [u.email for u in result.scalars().all()]

        from gneva.services.email import send_weekly_digest
        for email in user_emails:
            try:
                await send_weekly_digest(email, org_id)
            except Exception:
                logger.debug("Weekly digest failed for %s", email)

    # ------------------------------------------------------------------
    # Status report
    # ------------------------------------------------------------------
    async def generate_status_report(self, org_id: uuid.UUID) -> dict:
        """Generate an AI-powered weekly status report."""
        week_ago = datetime.utcnow() - timedelta(days=7)
        today = datetime.utcnow().date()

        async with async_session_factory() as db:
            meeting_count = (await db.execute(
                select(func.count()).select_from(Meeting)
                .where(Meeting.org_id == org_id, Meeting.created_at >= week_ago)
            )).scalar() or 0

            decisions = (await db.execute(
                select(Decision)
                .where(Decision.org_id == org_id, Decision.created_at >= week_ago)
            )).scalars().all()

            open_actions = (await db.execute(
                select(func.count()).select_from(ActionItem)
                .where(ActionItem.org_id == org_id, ActionItem.status.in_(["open", "in_progress"]))
            )).scalar() or 0

            overdue_count = (await db.execute(
                select(func.count()).select_from(ActionItem)
                .where(
                    ActionItem.org_id == org_id,
                    ActionItem.status.in_(["open", "in_progress"]),
                    ActionItem.due_date < today,
                )
            )).scalar() or 0

            completed = (await db.execute(
                select(func.count()).select_from(ActionItem)
                .where(
                    ActionItem.org_id == org_id,
                    ActionItem.completed_at >= week_ago,
                )
            )).scalar() or 0

        report = {
            "period": f"{(datetime.utcnow() - timedelta(days=7)).strftime('%b %d')} — {datetime.utcnow().strftime('%b %d, %Y')}",
            "meetings_held": meeting_count,
            "decisions_made": len(decisions),
            "decisions": [d.statement for d in decisions[:10]],
            "action_items_open": open_actions,
            "action_items_overdue": overdue_count,
            "action_items_completed": completed,
            "generated_at": datetime.utcnow().isoformat(),
        }

        # AI narrative summary
        if settings.anthropic_api_key and (decisions or meeting_count):
            from gneva.services import get_anthropic_client
            client = get_anthropic_client()
            context = (
                f"Meetings: {meeting_count}, Decisions: {len(decisions)}, "
                f"Open actions: {open_actions}, Overdue: {overdue_count}, Completed: {completed}\n"
                f"Key decisions: {'; '.join(d.statement for d in decisions[:5])}"
            )
            def _call():
                return client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=300,
                    system="Write a brief, professional weekly status update (3-5 sentences) for a team based on these metrics. Be specific and actionable.",
                    messages=[{"role": "user", "content": context}],
                )

            resp = await asyncio.to_thread(_call)
            report["narrative"] = resp.content[0].text

        return report

    # ------------------------------------------------------------------
    # Auto-schedule follow-ups after a meeting
    # ------------------------------------------------------------------
    async def auto_schedule_followups(self, meeting_id: uuid.UUID) -> list[dict]:
        """After a meeting ends, create follow-up reminders for action items without due dates."""
        followups = []

        async with async_session_factory() as db:
            items = (await db.execute(
                select(ActionItem)
                .where(ActionItem.meeting_id == meeting_id, ActionItem.status == "open")
            )).scalars().all()

            for item in items:
                if not item.due_date:
                    # Default: 1 week from now
                    item.due_date = (datetime.utcnow() + timedelta(days=7)).date()
                    followups.append({
                        "action_item_id": str(item.id),
                        "description": item.description,
                        "auto_due_date": str(item.due_date),
                    })

            if followups:
                await db.commit()

        logger.info("Auto-scheduled %d follow-ups for meeting %s", len(followups), meeting_id)
        return followups

    # ------------------------------------------------------------------
    # Suggest meetings
    # ------------------------------------------------------------------
    async def suggest_meetings(self, org_id: uuid.UUID) -> list[dict]:
        """Analyze patterns and suggest meetings that should happen."""
        suggestions = []

        async with async_session_factory() as db:
            # Find high-priority overdue items without recent meeting activity
            overdue_items = (await db.execute(
                select(ActionItem)
                .where(
                    ActionItem.org_id == org_id,
                    ActionItem.status.in_(["open", "in_progress"]),
                    ActionItem.priority == "high",
                    ActionItem.due_date < datetime.utcnow().date(),
                )
                .order_by(ActionItem.due_date.asc())
                .limit(10)
            )).scalars().all()

            # Find topics with many recent mentions but no decisions
            active_entities = (await db.execute(
                select(Entity)
                .where(
                    Entity.org_id == org_id,
                    Entity.type.in_(["project", "topic"]),
                    Entity.mention_count >= 5,
                )
                .order_by(Entity.last_seen.desc())
                .limit(10)
            )).scalars().all()

        if overdue_items:
            grouped: dict[str, list] = {}
            for item in overdue_items:
                key = str(item.assignee_id or "unassigned")
                grouped.setdefault(key, []).append(item.description)

            for assignee, descs in grouped.items():
                suggestions.append({
                    "type": "overdue_review",
                    "reason": f"{len(descs)} overdue high-priority items",
                    "details": descs[:3],
                    "suggested_title": "Overdue Items Review",
                    "urgency": "high",
                })

        for entity in active_entities:
            suggestions.append({
                "type": "topic_discussion",
                "reason": f"'{entity.name}' mentioned {entity.mention_count} times with no recent decision",
                "suggested_title": f"{entity.name} Discussion",
                "urgency": "medium",
            })

        return suggestions[:5]

    # ------------------------------------------------------------------
    # Calendar auto-join (stub — depends on calendar integration)
    # ------------------------------------------------------------------
    async def _check_calendar_autojoin(self) -> None:
        """Check for meetings starting in ~2 minutes and trigger bot auto-join."""
        now = datetime.utcnow()
        window_start = now + timedelta(minutes=1, seconds=30)
        window_end = now + timedelta(minutes=2, seconds=30)

        async with async_session_factory() as db:
            upcoming = (await db.execute(
                select(Meeting)
                .where(
                    Meeting.status == "scheduled",
                    Meeting.scheduled_at >= window_start,
                    Meeting.scheduled_at <= window_end,
                )
            )).scalars().all()
            candidates = [(meeting.title, meeting.scheduled_at) for meeting in upcoming]

        for title, scheduled_at in candidates:
            logger.info("Auto-join candidate: %s at %s", title, scheduled_at)
            # Bot auto-join would be triggered here via BotManager
            # This is a hook point for calendar integration

    # ------------------------------------------------------------------
    # Pattern detection
    # ------------------------------------------------------------------
    async def _detect_patterns(self, org_id: uuid.UUID) -> None:
        """Daily pattern analysis — find recurring themes, blocked items, etc."""
        week_ago = datetime.utcnow() - timedelta(days=7)

        async with async_session_factory() as db:
            # Find stale action items (open > 14 days)
            stale = (await db.execute(
                select(func.count()).select_from(ActionItem)
                .where(
                    ActionItem.org_id == org_id,
                    ActionItem.status.in_(["open", "in_progress"]),
                    ActionItem.created_at < datetime.utcnow() - timedelta(days=14),
                )
            )).scalar() or 0

            if stale > 0:
                logger.info("Org %s: %d stale action items (>14 days old)", org_id, stale)
