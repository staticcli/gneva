"""Slack integration service — post summaries, handle commands, send reminders."""

import asyncio
import hashlib
import hmac
import logging
import time
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.config import get_settings
from gneva.db import async_session_factory
from gneva.models.entity import ActionItem, Decision, Entity
from gneva.models.meeting import Meeting, MeetingSummary

logger = logging.getLogger(__name__)
settings = get_settings()

SLACK_API = "https://slack.com/api"


class SlackService:
    """Handles all Slack interactions: posting, commands, DMs."""

    def __init__(self):
        self._token = settings.slack_bot_token
        self._signing_secret = settings.slack_signing_secret
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------
    def verify_signature(self, body: bytes, timestamp: str, signature: str) -> bool:
        """Verify Slack request signature (v0 scheme)."""
        if abs(time.time() - int(timestamp)) > 300:
            return False
        base = f"v0:{timestamp}:{body.decode('utf-8')}"
        expected = "v0=" + hmac.new(
            self._signing_secret.encode(), base.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ------------------------------------------------------------------
    # Post meeting summary to a channel
    # ------------------------------------------------------------------
    async def post_meeting_summary(self, channel: str, meeting_id: uuid.UUID) -> dict:
        async with async_session_factory() as db:
            meeting = (await db.execute(
                select(Meeting).where(Meeting.id == meeting_id)
            )).scalar_one_or_none()
            if not meeting:
                return {"ok": False, "error": "meeting_not_found"}

            summary = (await db.execute(
                select(MeetingSummary).where(MeetingSummary.meeting_id == meeting_id)
            )).scalar_one_or_none()
            if not summary:
                return {"ok": False, "error": "summary_not_ready"}

        title = meeting.title or "Untitled Meeting"
        decisions_text = "\n".join(f"  • {d}" for d in (summary.key_decisions or [])) or "_None recorded_"
        topics_text = ", ".join(summary.topics_covered or []) or "_None_"

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f"Meeting Recap: {title}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*TL;DR:* {summary.tldr}"}},
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Key Decisions:*\n{decisions_text}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Topics:* {topics_text}"}},
            {"type": "context", "elements": [
                {"type": "mrkdwn", "text": f"Sentiment: {summary.sentiment or 'neutral'} | Follow-up needed: {'Yes' if summary.follow_up_needed else 'No'}"}
            ]},
        ]
        return await self._post_message(channel, blocks=blocks, text=f"Meeting Recap: {title}")

    # ------------------------------------------------------------------
    # Post action items
    # ------------------------------------------------------------------
    async def post_action_items(self, channel: str, meeting_id: uuid.UUID) -> dict:
        async with async_session_factory() as db:
            items = (await db.execute(
                select(ActionItem).where(ActionItem.meeting_id == meeting_id)
            )).scalars().all()

        if not items:
            return await self._post_message(channel, text="No action items for this meeting.")

        lines = []
        for i, a in enumerate(items, 1):
            due = f" (due {a.due_date})" if a.due_date else ""
            priority_emoji = {"high": ":red_circle:", "medium": ":large_yellow_circle:", "low": ":white_circle:"}.get(a.priority, ":white_circle:")
            lines.append(f"{priority_emoji} *{i}.* {a.description}{due} — _{a.status}_")

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "Action Items"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}},
        ]
        return await self._post_message(channel, blocks=blocks, text="Action Items")

    # ------------------------------------------------------------------
    # Slash command handler
    # ------------------------------------------------------------------
    async def handle_slash_command(self, text: str, user_id: str, channel: str, org_id: str = "") -> dict:
        """Handle /gneva slash commands. Returns Slack response payload.

        Args:
            org_id: Organization ID to scope queries. Required for data isolation.
                    TODO: Map Slack workspace (team_id) to org_id automatically.
        """
        parts = text.strip().split(maxsplit=1)
        command = parts[0].lower() if parts else "help"
        arg = parts[1] if len(parts) > 1 else ""

        if command == "ask" and arg:
            return await self._cmd_ask(arg, channel, org_id)
        elif command == "actions":
            return await self._cmd_actions(channel, org_id)
        elif command == "meetings":
            return await self._cmd_meetings(channel, org_id)
        elif command == "search" and arg:
            return await self._cmd_search(arg, channel, org_id)
        else:
            return {
                "response_type": "ephemeral",
                "text": (
                    "*Gneva Commands:*\n"
                    "• `/gneva ask <question>` — Ask anything from org memory\n"
                    "• `/gneva actions` — List open action items\n"
                    "• `/gneva meetings` — Recent meetings\n"
                    "• `/gneva search <query>` — Search entities"
                ),
            }

    async def _cmd_ask(self, question: str, channel: str, org_id: str = "") -> dict:
        """Answer a question from org memory via Claude."""
        escaped_q = question.replace("%", r"\%").replace("_", r"\_")
        async with async_session_factory() as db:
            query = select(Entity).where(Entity.name.ilike(f"%{escaped_q}%"))
            if org_id:
                query = query.where(Entity.org_id == org_id)
            entities = (await db.execute(
                query
                .order_by(Entity.mention_count.desc())
                .limit(5)
            )).scalars().all()

        context = "\n".join(
            f"[{e.type}] {e.name}: {e.description or 'N/A'}" for e in entities
        ) or "No matching context found."

        if not settings.anthropic_api_key:
            return {"response_type": "ephemeral", "text": f"_Context found:_\n{context}\n\n(AI answer unavailable — Anthropic key not set)"}

        from gneva.services import get_anthropic_client
        client = get_anthropic_client()

        def _call():
            return client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system="You are Gneva, an AI team member. Answer concisely based on the context provided.",
                messages=[{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
            )

        resp = await asyncio.to_thread(_call)
        return {"response_type": "in_channel", "text": resp.content[0].text}

    async def _cmd_actions(self, channel: str, org_id: str = "") -> dict:
        async with async_session_factory() as db:
            query = select(ActionItem).where(ActionItem.status.in_(["open", "in_progress"]))
            if org_id:
                query = query.where(ActionItem.org_id == org_id)
            items = (await db.execute(
                query
                .order_by(ActionItem.created_at.desc())
                .limit(10)
            )).scalars().all()

        if not items:
            return {"response_type": "ephemeral", "text": "No open action items."}

        lines = [f"• {a.description} — _{a.priority}_ / _{a.status}_" for a in items]
        return {"response_type": "in_channel", "text": "*Open Action Items:*\n" + "\n".join(lines)}

    async def _cmd_meetings(self, channel: str, org_id: str = "") -> dict:
        async with async_session_factory() as db:
            query = select(Meeting)
            if org_id:
                query = query.where(Meeting.org_id == org_id)
            meetings = (await db.execute(
                query
                .order_by(Meeting.created_at.desc())
                .limit(5)
            )).scalars().all()

        if not meetings:
            return {"response_type": "ephemeral", "text": "No meetings recorded yet."}

        lines = []
        for m in meetings:
            date_str = m.started_at.strftime("%b %d %H:%M") if m.started_at else "Scheduled"
            lines.append(f"• *{m.title or 'Untitled'}* — {date_str} ({m.status})")
        return {"response_type": "in_channel", "text": "*Recent Meetings:*\n" + "\n".join(lines)}

    async def _cmd_search(self, query: str, channel: str, org_id: str = "") -> dict:
        escaped_q = query.replace("%", r"\%").replace("_", r"\_")
        async with async_session_factory() as db:
            stmt = select(Entity).where(Entity.name.ilike(f"%{escaped_q}%"))
            if org_id:
                stmt = stmt.where(Entity.org_id == org_id)
            entities = (await db.execute(
                stmt
                .order_by(Entity.mention_count.desc())
                .limit(10)
            )).scalars().all()

        if not entities:
            return {"response_type": "ephemeral", "text": f"No entities found matching '{query}'."}

        lines = [f"• [{e.type}] *{e.name}* — {e.description or 'No description'} ({e.mention_count} mentions)" for e in entities]
        return {"response_type": "in_channel", "text": f"*Search results for '{query}':*\n" + "\n".join(lines)}

    # ------------------------------------------------------------------
    # Direct messages
    # ------------------------------------------------------------------
    async def send_dm(self, slack_user_id: str, message: str) -> dict:
        """Open a DM channel and send a message."""
        async with httpx.AsyncClient() as client:
            conv = await client.post(
                f"{SLACK_API}/conversations.open",
                headers=self._headers,
                json={"users": slack_user_id},
            )
            conv_data = conv.json()
            if not conv_data.get("ok"):
                return conv_data
            channel_id = conv_data["channel"]["id"]
        return await self._post_message(channel_id, text=message)

    async def send_action_reminder(self, slack_user_id: str, action_item: ActionItem) -> dict:
        """Send a DM reminder about a due/overdue action item."""
        due_str = str(action_item.due_date) if action_item.due_date else "no due date"
        today = datetime.utcnow().date()
        overdue = action_item.due_date and action_item.due_date < today
        urgency = ":rotating_light: *OVERDUE*" if overdue else ":bell: *Reminder*"

        msg = (
            f"{urgency}\n"
            f"*Action:* {action_item.description}\n"
            f"*Due:* {due_str}\n"
            f"*Priority:* {action_item.priority}\n"
            f"*Status:* {action_item.status}"
        )
        return await self.send_dm(slack_user_id, msg)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _post_message(self, channel: str, text: str, blocks: list | None = None) -> dict:
        payload: dict = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SLACK_API}/chat.postMessage",
                headers=self._headers,
                json=payload,
                timeout=10,
            )
            data = resp.json()
            if not data.get("ok"):
                logger.error("Slack post failed: %s", data.get("error"))
            return data
