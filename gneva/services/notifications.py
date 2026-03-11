"""Notification service — create, send, and manage notifications."""

import asyncio
import logging
import smtplib
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.models.calendar import Notification, FollowUp
from gneva.models.entity import ActionItem
from gneva.models.meeting import Meeting
from gneva.models.user import User
from gneva.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def create_notification(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: str,
    channel: str = "in_app",
    meeting_id: uuid.UUID | None = None,
    action_item_id: uuid.UUID | None = None,
) -> Notification:
    """Create a notification record in the database."""
    notification = Notification(
        org_id=org_id,
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        channel=channel,
        meeting_id=meeting_id,
        action_item_id=action_item_id,
    )
    db.add(notification)
    await db.flush()

    if channel == "email":
        try:
            await send_email_notification(notification, db)
        except Exception as e:
            logger.error(f"Failed to send email notification {notification.id}: {e}")

    return notification


async def send_email_notification(notification: Notification, db: AsyncSession) -> bool:
    """Send an email notification via SMTP. Returns True on success."""
    if not settings.smtp_host:
        logger.warning("SMTP not configured — skipping email notification")
        return False

    # Look up user email
    result = await db.execute(
        select(User).where(User.id == notification.user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        logger.error(f"User {notification.user_id} not found for email notification")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = notification.title
    msg["From"] = settings.smtp_from
    msg["To"] = user.email

    text_body = notification.body
    safe_title = escape(notification.title)
    safe_body = escape(notification.body)
    html_body = f"""
    <html>
    <body style="font-family: sans-serif; color: #333;">
        <h2 style="color: #6C5CE7;">{safe_title}</h2>
        <p>{safe_body}</p>
        <hr style="border: 1px solid #eee;">
        <p style="font-size: 12px; color: #999;">
            Sent by Gneva Meeting Intelligence
        </p>
    </body>
    </html>
    """
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    def _do_send():
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.ehlo()
            if settings.smtp_port == 587:
                server.starttls()
                server.ehlo()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

    try:
        await asyncio.to_thread(_do_send)

        notification.sent_at = datetime.utcnow()
        await db.flush()
        logger.info(f"Email notification sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"SMTP send failed for {user.email}: {e}")
        return False


async def get_unread(db: AsyncSession, user_id: str) -> list[Notification]:
    """Get all unread notifications for a user, most recent first."""
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.user_id == user_id,
                Notification.read.is_(False),
            )
        ).order_by(Notification.created_at.desc())
    )
    return list(result.scalars().all())


async def get_all_notifications(
    db: AsyncSession, user_id: str, offset: int = 0, limit: int = 50
) -> tuple[list[Notification], int]:
    """Get all notifications for a user, unread first, then by recency."""
    base_q = select(Notification).where(Notification.user_id == user_id)
    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar()

    result = await db.execute(
        base_q.order_by(Notification.read.asc(), Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result.scalars().all()), total


async def mark_read(db: AsyncSession, notification_id: str, user_id: str) -> bool:
    """Mark a single notification as read. Returns True if found and updated."""
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        return False
    notification.read = True
    await db.flush()
    return True


async def mark_all_read(db: AsyncSession, user_id: str) -> int:
    """Mark all notifications as read for a user. Returns count updated."""
    result = await db.execute(
        update(Notification)
        .where(
            and_(
                Notification.user_id == user_id,
                Notification.read.is_(False),
            )
        )
        .values(read=True)
    )
    await db.flush()
    return result.rowcount


async def get_unread_count(db: AsyncSession, user_id: str) -> int:
    """Get count of unread notifications for badge display."""
    result = await db.execute(
        select(func.count()).where(
            and_(
                Notification.user_id == user_id,
                Notification.read.is_(False),
            )
        )
    )
    return result.scalar() or 0


async def create_meeting_complete_notifications(
    db: AsyncSession, meeting_id: str
) -> list[Notification]:
    """After pipeline completes, notify all org members about the meeting."""
    result = await db.execute(
        select(Meeting).where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        logger.warning(f"Meeting {meeting_id} not found for notification")
        return []

    # Get all users in the org
    users_result = await db.execute(
        select(User).where(User.org_id == meeting.org_id)
    )
    users = users_result.scalars().all()

    notifications = []
    for user in users:
        title_text = meeting.title or "Untitled Meeting"
        notif = await create_notification(
            db,
            org_id=meeting.org_id,
            user_id=user.id,
            type="meeting_complete",
            title=f"Meeting processed: {title_text}",
            body=f"Notes, action items, and insights are ready for '{title_text}'.",
            channel="in_app",
            meeting_id=meeting.id,
        )
        notifications.append(notif)

    return notifications


async def create_action_item_notifications(
    db: AsyncSession, meeting_id: str
) -> list[Notification]:
    """Notify assignees of new action items from a meeting."""
    result = await db.execute(
        select(ActionItem).where(
            and_(
                ActionItem.meeting_id == meeting_id,
                ActionItem.assignee_id.isnot(None),
            )
        )
    )
    items = result.scalars().all()

    meeting_result = await db.execute(
        select(Meeting).where(Meeting.id == meeting_id)
    )
    meeting = meeting_result.scalar_one_or_none()
    meeting_title = meeting.title if meeting else "a meeting"

    notifications = []
    for item in items:
        due_str = f" (due {item.due_date})" if item.due_date else ""
        notif = await create_notification(
            db,
            org_id=item.org_id,
            user_id=item.assignee_id,
            type="action_item_due",
            title=f"New action item from {meeting_title}",
            body=f"{item.description}{due_str}",
            channel="in_app",
            meeting_id=item.meeting_id,
            action_item_id=item.id,
        )
        notifications.append(notif)

    return notifications


async def check_overdue_actions(db: AsyncSession, org_id: uuid.UUID) -> list[Notification]:
    """Find overdue action items and create follow-up notifications."""
    now = datetime.utcnow().date()

    result = await db.execute(
        select(ActionItem).where(
            and_(
                ActionItem.org_id == org_id,
                ActionItem.status == "open",
                ActionItem.due_date.isnot(None),
                ActionItem.due_date < now,
                ActionItem.assignee_id.isnot(None),
            )
        )
    )
    overdue_items = result.scalars().all()

    notifications = []
    for item in overdue_items:
        # Check if we already sent a follow-up reminder today
        existing = await db.execute(
            select(func.count()).where(
                and_(
                    Notification.action_item_id == item.id,
                    Notification.type == "follow_up_reminder",
                    func.date(Notification.created_at) == now,
                )
            )
        )
        if existing.scalar() > 0:
            continue

        days_overdue = (now - item.due_date).days
        notif = await create_notification(
            db,
            org_id=org_id,
            user_id=item.assignee_id,
            type="follow_up_reminder",
            title=f"Overdue action item ({days_overdue}d)",
            body=f"Action item is {days_overdue} day(s) overdue: {item.description}",
            channel="in_app",
            action_item_id=item.id,
        )
        notifications.append(notif)

        # Also create/update a FollowUp record
        follow_up = FollowUp(
            org_id=org_id if isinstance(org_id, uuid.UUID) else uuid.UUID(org_id),
            action_item_id=item.id,
            meeting_id=item.meeting_id,
            assigned_to=item.assignee_id,
            type="action_reminder",
            description=f"Overdue: {item.description}",
            due_date=item.due_date,
            status="sent",
            reminder_count=1,
            last_reminded_at=datetime.utcnow(),
        )
        db.add(follow_up)

    await db.flush()
    return notifications
