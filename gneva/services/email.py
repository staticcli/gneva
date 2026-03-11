"""Email digest service — meeting recaps, weekly digests, action reminders."""

import asyncio
import logging
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.config import get_settings
from gneva.db import async_session_factory
from gneva.models.entity import ActionItem, Decision
from gneva.models.meeting import Meeting, MeetingSummary

logger = logging.getLogger(__name__)
settings = get_settings()


def _html_wrapper(title: str, body: str) -> str:
    """Wrap body HTML in a styled email template."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a2e; margin: 0; padding: 0; background: #f5f5f5; }}
  .container {{ max-width: 600px; margin: 20px auto; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
  .header {{ background: #6366f1; color: #fff; padding: 24px; }}
  .header h1 {{ margin: 0; font-size: 20px; }}
  .content {{ padding: 24px; }}
  .section {{ margin-bottom: 20px; }}
  .section h2 {{ font-size: 16px; color: #6366f1; margin-bottom: 8px; }}
  .item {{ padding: 8px 0; border-bottom: 1px solid #eee; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
  .badge-high {{ background: #fee2e2; color: #dc2626; }}
  .badge-medium {{ background: #fef3c7; color: #d97706; }}
  .badge-low {{ background: #dbeafe; color: #2563eb; }}
  .badge-overdue {{ background: #dc2626; color: #fff; }}
  .footer {{ padding: 16px 24px; background: #f9fafb; font-size: 12px; color: #6b7280; text-align: center; }}
</style></head><body>
<div class="container">
  <div class="header"><h1>{escape(title)}</h1></div>
  <div class="content">{body}</div>
  <div class="footer">Sent by Gneva &mdash; your AI team member</div>
</div></body></html>"""


def _send(to: str, subject: str, html: str) -> None:
    """Send an HTML email via SMTP."""
    # Prevent header injection by stripping newlines
    to = to.replace("\r", "").replace("\n", "")
    subject = subject.replace("\r", "").replace("\n", "")

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_port != 25:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from, to, msg.as_string())
        logger.info("Email sent to %s: %s", to, subject)
    except Exception:
        logger.exception("Failed to send email to %s", to)
        raise


async def send_meeting_recap(user_email: str, meeting_id: uuid.UUID) -> None:
    """Send HTML recap email with summary, action items, and decisions."""
    async with async_session_factory() as db:
        meeting = (await db.execute(
            select(Meeting).where(Meeting.id == meeting_id)
        )).scalar_one_or_none()
        if not meeting:
            logger.warning("Meeting %s not found for recap email", meeting_id)
            return

        summary = (await db.execute(
            select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_id)
        )).scalar_one_or_none()

        items = (await db.execute(
            select(ActionItem).where(ActionItem.meeting_id == meeting_id)
        )).scalars().all()

        decisions = (await db.execute(
            select(Decision).where(Decision.meeting_id == meeting_id)
        )).scalars().all()

    title = escape(meeting.title or "Untitled Meeting")
    date_str = meeting.started_at.strftime("%B %d, %Y") if meeting.started_at else "N/A"

    tldr_text = escape(summary.tldr) if summary and summary.tldr else "Summary not available yet."
    body = f'<div class="section"><h2>Summary</h2><p>{tldr_text}</p></div>'

    if decisions:
        dec_html = "".join(f'<div class="item">{escape(d.statement)}</div>' for d in decisions)
        body += f'<div class="section"><h2>Decisions</h2>{dec_html}</div>'

    if items:
        items_html = ""
        for a in items:
            badge_cls = f"badge-{escape(a.priority)}"
            due = f" &mdash; due {a.due_date}" if a.due_date else ""
            items_html += f'<div class="item"><span class="badge {badge_cls}">{escape(a.priority)}</span> {escape(a.description)}{due}</div>'
        body += f'<div class="section"><h2>Action Items</h2>{items_html}</div>'

    if summary and summary.topics_covered:
        topics = ", ".join(escape(t) for t in summary.topics_covered)
        body += f'<div class="section"><h2>Topics Covered</h2><p>{topics}</p></div>'

    html = _html_wrapper(f"Meeting Recap: {title} ({date_str})", body)
    await asyncio.to_thread(_send, user_email, f"[Gneva] Meeting Recap: {title}", html)


async def send_weekly_digest(user_email: str, org_id: uuid.UUID) -> None:
    """Send weekly summary: meetings held, key decisions, overdue items."""
    week_ago = datetime.utcnow() - timedelta(days=7)
    today = datetime.utcnow().date()

    async with async_session_factory() as db:
        meetings = (await db.execute(
            select(Meeting)
            .where(Meeting.org_id == org_id, Meeting.created_at >= week_ago)
            .order_by(Meeting.created_at.desc())
        )).scalars().all()

        decisions = (await db.execute(
            select(Decision)
            .where(Decision.org_id == org_id, Decision.created_at >= week_ago)
            .order_by(Decision.created_at.desc())
        )).scalars().all()

        overdue = (await db.execute(
            select(ActionItem)
            .where(
                ActionItem.org_id == org_id,
                ActionItem.status.in_(["open", "in_progress"]),
                ActionItem.due_date < today,
            )
        )).scalars().all()

        open_items = (await db.execute(
            select(func.count())
            .select_from(ActionItem)
            .where(ActionItem.org_id == org_id, ActionItem.status.in_(["open", "in_progress"]))
        )).scalar() or 0

    body = f'<div class="section"><h2>This Week at a Glance</h2>'
    body += f"<p><strong>{len(meetings)}</strong> meetings &bull; <strong>{len(decisions)}</strong> decisions &bull; <strong>{open_items}</strong> open action items</p></div>"

    if meetings:
        m_html = "".join(
            f'<div class="item"><strong>{escape(m.title or "Untitled")}</strong> &mdash; {m.started_at.strftime("%b %d") if m.started_at else "Scheduled"}</div>'
            for m in meetings
        )
        body += f'<div class="section"><h2>Meetings</h2>{m_html}</div>'

    if decisions:
        d_html = "".join(f'<div class="item">{escape(d.statement)}</div>' for d in decisions[:10])
        body += f'<div class="section"><h2>Key Decisions</h2>{d_html}</div>'

    if overdue:
        o_html = ""
        for a in overdue:
            o_html += f'<div class="item"><span class="badge badge-overdue">OVERDUE</span> {escape(a.description)} (due {a.due_date})</div>'
        body += f'<div class="section"><h2>Overdue Action Items</h2>{o_html}</div>'

    html = _html_wrapper("Weekly Digest", body)
    week_str = datetime.utcnow().strftime("%b %d, %Y")
    await asyncio.to_thread(_send, user_email, f"[Gneva] Weekly Digest — {week_str}", html)


async def send_action_reminder(user_email: str, action_item: ActionItem) -> None:
    """Send reminder email for a due or overdue action item."""
    today = datetime.utcnow().date()
    overdue = action_item.due_date and action_item.due_date < today
    status_label = "OVERDUE" if overdue else "Due Today"
    badge_cls = "badge-overdue" if overdue else "badge-medium"

    body = (
        f'<div class="section">'
        f'<p><span class="badge {badge_cls}">{status_label}</span></p>'
        f"<p><strong>Action:</strong> {escape(action_item.description)}</p>"
        f"<p><strong>Due:</strong> {action_item.due_date or 'No due date'}</p>"
        f"<p><strong>Priority:</strong> {escape(action_item.priority)}</p>"
        f"</div>"
    )
    html = _html_wrapper(f"Action Item {status_label}", body)
    await asyncio.to_thread(_send, user_email, f"[Gneva] {status_label}: {escape(action_item.description[:60])}", html)
