"""Conversation tool definitions and executors for in-meeting actions.

Gneva can use these tools during live meetings to take real actions:
create action items, look up memory, bookmark moments, check statuses, etc.
"""

import asyncio
import logging
import time
import uuid
from datetime import date, datetime, timedelta

from dateutil import parser as dateutil_parser

logger = logging.getLogger(__name__)


def _escape_like(s: str) -> str:
    """Escape SQL LIKE/ILIKE wildcard characters."""
    return s.replace("%", r"\%").replace("_", r"\_")


# ---------------------------------------------------------------------------
# Tool definitions (Anthropic tool_use format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "create_action_item",
        "description": (
            "Create a new action item from the meeting. Use when someone says "
            "something like 'add an action item for Sarah to finish the API by Friday' "
            "or 'note that down as a to-do'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "What needs to be done.",
                },
                "assignee_name": {
                    "type": "string",
                    "description": "Name of the person responsible. Leave empty if unassigned.",
                },
                "due_date": {
                    "type": "string",
                    "description": (
                        "When it's due, in natural language like 'Friday', 'next week', "
                        "'March 15', 'end of sprint'. Leave empty if no deadline mentioned."
                    ),
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Priority level. Default medium.",
                },
            },
            "required": ["description"],
        },
    },
    {
        "name": "update_action_item",
        "description": (
            "Update the status of an existing action item. Use when someone says "
            "'mark the API migration as done' or 'that deploy task is in progress'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "search_text": {
                    "type": "string",
                    "description": "Text to search for in existing action items.",
                },
                "new_status": {
                    "type": "string",
                    "enum": ["open", "in_progress", "done"],
                    "description": "New status for the action item.",
                },
            },
            "required": ["search_text", "new_status"],
        },
    },
    {
        "name": "query_action_items",
        "description": (
            "Look up action items. Use when someone asks 'what's overdue?', "
            "'what does Sarah have on her plate?', or 'what are our open items?'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filter": {
                    "type": "string",
                    "enum": ["all", "open", "overdue", "done"],
                    "description": "Which action items to return.",
                },
                "assignee_name": {
                    "type": "string",
                    "description": "Filter by assignee name. Leave empty for all.",
                },
            },
            "required": ["filter"],
        },
    },
    {
        "name": "search_memory",
        "description": (
            "Search Gneva's organizational memory for past decisions, discussions, "
            "entities, and meeting history. Use when someone asks 'what did we decide "
            "about pricing?' or 'when did we last talk about the migration?'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for in organizational memory.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "bookmark_moment",
        "description": (
            "Pin/bookmark the current moment in the meeting. Use when someone says "
            "'bookmark that', 'pin that', 'mark this moment', or 'save that point'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Optional label for the bookmark. Can be empty.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "describe_screen",
        "description": (
            "Look at what's currently being shared on screen. Use when someone asks "
            "'what's on the screen?', 'can you see this?', 'what does this show?', "
            "or references something visual you should look at."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the web for current information. Use when someone asks about "
            "something you don't know, needs a fact check, wants current data "
            "(stock prices, news, release dates, competitor info), or when the "
            "answer requires up-to-date information you don't have."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Be specific and concise.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "quick_research",
        "description": (
            "Do a deeper research pass on a topic — combines web search with analysis. "
            "Use when someone says 'look into that', 'can you research X', "
            "'find out about Y', or needs a synthesized answer from multiple sources. "
            "Takes longer than web_search but gives a more complete answer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic or question to research.",
                },
                "context": {
                    "type": "string",
                    "description": "Additional context about what specifically to look for.",
                },
            },
            "required": ["topic"],
        },
    },
    {
        "name": "fetch_url",
        "description": (
            "Fetch and read the content of a specific URL. Use when someone shares "
            "a link in the meeting or says 'check this link' or 'look at this page'. "
            "Returns a summary of the page content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch and read.",
                },
            },
            "required": ["url"],
        },
    },
    # --- Multi-agent orchestrator tools ---
    {
        "name": "summon_agent",
        "description": (
            "Bring a specialist agent into the meeting. Use when the conversation "
            "needs a specific expert — e.g. 'let's get Cipher in here to look at the AWS issue' "
            "or when you detect a topic that needs specialist knowledge. "
            "Available agents: vex (strategy), prism (data), echo (memory), sage (facilitation), "
            "nexus (sales), cipher (cloud), forge (devops), shield (security), ledger (finance), "
            "pulse (product), atlas (legal), helix (engineering), orbit (customer success), "
            "spark (communications), quantum (AI/ML)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "The agent's name (lowercase): cipher, shield, helix, etc.",
                },
                "reason": {
                    "type": "string",
                    "description": "Brief reason for summoning this agent.",
                },
            },
            "required": ["agent_name", "reason"],
        },
    },
    {
        "name": "dismiss_agent",
        "description": (
            "Remove a specialist agent from the meeting. Use when their expertise "
            "is no longer needed, e.g. 'thanks Cipher, we're moving on'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "The agent's name to dismiss.",
                },
            },
            "required": ["agent_name"],
        },
    },
    {
        "name": "ask_agent",
        "description": (
            "Privately consult a specialist agent — they answer you but don't speak "
            "publicly. Use when you need expert input to inform YOUR response. "
            "The agent's answer comes back to you; you decide what to relay to the meeting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Which specialist to ask.",
                },
                "question": {
                    "type": "string",
                    "description": "The question to ask the specialist.",
                },
            },
            "required": ["agent_name", "question"],
        },
    },
    {
        "name": "delegate_question",
        "description": (
            "Let a specialist agent answer a meeting question directly — they speak publicly. "
            "Use when someone asks a domain-specific question best handled by a specialist, "
            "e.g. 'Cipher, can you explain the VPC setup?'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Which specialist should answer.",
                },
                "question": {
                    "type": "string",
                    "description": "The question for the specialist to answer publicly.",
                },
            },
            "required": ["agent_name", "question"],
        },
    },
    {
        "name": "request_deliberation",
        "description": (
            "Ask multiple specialist agents to weigh in on a question simultaneously, "
            "then synthesize their answers. Use for complex questions that span domains — "
            "e.g. 'should we rewrite the auth system?' might need helix + shield + forge."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The question to deliberate on.",
                },
                "agent_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of agent names to consult (2-4 recommended).",
                },
            },
            "required": ["question", "agent_names"],
        },
    },
    {
        "name": "meeting_pulse",
        "description": (
            "Get a quick pulse on the current meeting — who's active, what agents are present, "
            "and key stats. Use when someone asks 'who's in the room?' or 'what agents are active?'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "generate_briefing",
        "description": (
            "Generate a pre-meeting briefing from past meetings and organizational memory. "
            "Use at the start of a meeting or when someone asks 'what should we know going in?' "
            "or 'what happened last time?'. Pulls from action items, decisions, and meeting history."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "focus_topics": {
                    "type": "string",
                    "description": "Optional focus areas for the briefing.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "close_meeting_summary",
        "description": (
            "Generate a structured end-of-meeting summary. Use when the meeting is wrapping up "
            "or someone says 'let's wrap up' / 'can you summarize?' / 'what did we cover?'. "
            "Summarizes decisions, action items, open questions, and next steps."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "additional_notes": {
                    "type": "string",
                    "description": "Any additional context to include in the summary.",
                },
            },
            "required": [],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool executors
# ---------------------------------------------------------------------------

async def execute_tool(
    tool_name: str,
    tool_input: dict,
    org_id: str | None,
    meeting_id: str | None,
    transcript_buffer: list[dict] | None = None,
    meeting_start_time: float | None = None,
    screen_capture=None,
    agent_router=None,
) -> str:
    """Execute a tool and return a text result for Claude to verbalize."""
    try:
        if tool_name == "create_action_item":
            return await _create_action_item(tool_input, org_id, meeting_id)
        elif tool_name == "update_action_item":
            return await _update_action_item(tool_input, org_id)
        elif tool_name == "query_action_items":
            return await _query_action_items(tool_input, org_id)
        elif tool_name == "search_memory":
            return await _search_memory(tool_input, org_id)
        elif tool_name == "bookmark_moment":
            return await _bookmark_moment(
                tool_input, org_id, meeting_id,
                transcript_buffer, meeting_start_time,
            )
        elif tool_name == "describe_screen":
            return await _describe_screen(screen_capture)
        elif tool_name == "web_search":
            return await _web_search(tool_input)
        elif tool_name == "quick_research":
            return await _quick_research(tool_input)
        elif tool_name == "fetch_url":
            return await _fetch_url(tool_input)
        # --- Multi-agent orchestrator tools ---
        elif tool_name == "summon_agent":
            return await _summon_agent(tool_input, agent_router)
        elif tool_name == "dismiss_agent":
            return await _dismiss_agent(tool_input, agent_router)
        elif tool_name == "ask_agent":
            return await _ask_agent(tool_input, agent_router, transcript_buffer)
        elif tool_name == "delegate_question":
            return await _delegate_question(tool_input, agent_router, transcript_buffer)
        elif tool_name == "request_deliberation":
            return await _request_deliberation(tool_input, agent_router, transcript_buffer)
        elif tool_name == "meeting_pulse":
            return await _meeting_pulse(agent_router)
        elif tool_name == "generate_briefing":
            return await _generate_briefing(tool_input, org_id, meeting_id, transcript_buffer)
        elif tool_name == "close_meeting_summary":
            return await _close_meeting_summary(
                tool_input, org_id, meeting_id, transcript_buffer, meeting_start_time, agent_router
            )
        else:
            return f"Unknown tool: {tool_name}"
    except Exception as e:
        logger.error(f"Tool execution failed [{tool_name}]: {e}", exc_info=True)
        return f"Sorry, that tool didn't work right now. Please try again."


def _parse_due_date(text: str | None) -> date | None:
    """Parse natural language due dates relative to today."""
    if not text:
        return None
    text = text.strip().lower()
    today = date.today()

    # Common relative dates
    if text in ("today",):
        return today
    if text in ("tomorrow",):
        return today + timedelta(days=1)
    if text in ("next week",):
        return today + timedelta(days=7)
    if text in ("end of week", "eow", "this friday"):
        days_until_fri = (4 - today.weekday()) % 7
        if days_until_fri == 0:
            days_until_fri = 7
        return today + timedelta(days=days_until_fri)
    if text in ("end of month", "eom"):
        if today.month == 12:
            return date(today.year + 1, 1, 1) - timedelta(days=1)
        return date(today.year, today.month + 1, 1) - timedelta(days=1)

    # Day names
    day_names = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }
    for name, dow in day_names.items():
        if name in text:
            days_ahead = (dow - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            if "next" in text:
                days_ahead += 7
            return today + timedelta(days=days_ahead)

    # Try dateutil as fallback
    try:
        parsed = dateutil_parser.parse(text, fuzzy=True)
        return parsed.date()
    except (ValueError, OverflowError):
        return None


async def _find_person_entity(session, org_id: str, name: str):
    """Find a person entity by fuzzy name match."""
    from gneva.models.entity import Entity
    from sqlalchemy import select

    name_lower = name.strip().lower()
    result = await session.execute(
        select(Entity).where(
            Entity.org_id == uuid.UUID(org_id),
            Entity.type == "person",
            Entity.canonical.ilike(f"%{_escape_like(name_lower)}%"),
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def _create_action_item(tool_input: dict, org_id: str | None, meeting_id: str | None) -> str:
    """Create an action item in the database."""
    from gneva.db import async_session_factory
    from gneva.models.entity import ActionItem, Entity
    from gneva.models.compat import new_uuid

    if not org_id:
        return "Cannot create action item without organization context."

    description = tool_input.get("description", "").strip()
    if not description:
        return "No description provided for the action item."

    assignee_name = tool_input.get("assignee_name", "").strip()
    due_date = _parse_due_date(tool_input.get("due_date"))
    priority = tool_input.get("priority", "medium")

    async with async_session_factory() as session:
        # Create an entity for this action item
        entity = Entity(
            id=new_uuid(),
            org_id=uuid.UUID(org_id),
            type="action_item",
            name=description[:100],
            canonical=description[:100].lower(),
            description=description,
            metadata_json={"source": "voice_command", "assignee_name": assignee_name},
        )
        session.add(entity)

        # Find assignee if named
        assignee_id = None
        if assignee_name:
            person = await _find_person_entity(session, org_id, assignee_name)
            if person:
                assignee_id = None  # ActionItem.assignee_id is FK to users, not entities

        action = ActionItem(
            id=new_uuid(),
            entity_id=entity.id,
            org_id=uuid.UUID(org_id),
            meeting_id=uuid.UUID(meeting_id) if meeting_id else new_uuid(),
            description=description,
            assignee_id=assignee_id,
            due_date=due_date,
            priority=priority,
            status="open",
        )
        session.add(action)
        await session.commit()

    parts = [f"Created action item: {description}"]
    if assignee_name:
        parts.append(f"Assigned to {assignee_name}")
    if due_date:
        parts.append(f"Due {due_date.strftime('%A %B %d')}")
    parts.append(f"Priority: {priority}")
    return ". ".join(parts) + "."


async def _update_action_item(tool_input: dict, org_id: str | None) -> str:
    """Update an existing action item's status."""
    from gneva.db import async_session_factory
    from gneva.models.entity import ActionItem
    from sqlalchemy import select

    if not org_id:
        return "Cannot update action items without organization context."

    search_text = tool_input.get("search_text", "").strip().lower()
    new_status = tool_input.get("new_status", "done")

    async with async_session_factory() as session:
        result = await session.execute(
            select(ActionItem).where(
                ActionItem.org_id == uuid.UUID(org_id),
                ActionItem.description.ilike(f"%{_escape_like(search_text)}%"),
            ).order_by(ActionItem.created_at.desc()).limit(1)
        )
        action = result.scalar_one_or_none()

        if not action:
            return f"Could not find an action item matching '{search_text}'."

        old_status = action.status
        action.status = new_status
        if new_status == "done":
            action.completed_at = datetime.utcnow()
        await session.commit()

        return (
            f"Updated '{action.description[:60]}' from {old_status} to {new_status}."
        )


async def _query_action_items(tool_input: dict, org_id: str | None) -> str:
    """Query action items with optional filtering."""
    from gneva.db import async_session_factory
    from gneva.models.entity import ActionItem, Entity
    from sqlalchemy import select

    if not org_id:
        return "Cannot query action items without organization context."

    filter_type = tool_input.get("filter", "open")
    assignee_name = tool_input.get("assignee_name", "").strip().lower()

    async with async_session_factory() as session:
        query = select(ActionItem).where(ActionItem.org_id == uuid.UUID(org_id))

        if filter_type == "open":
            query = query.where(ActionItem.status.in_(["open", "in_progress"]))
        elif filter_type == "overdue":
            query = query.where(
                ActionItem.status.in_(["open", "in_progress"]),
                ActionItem.due_date < date.today(),
            )
        elif filter_type == "done":
            query = query.where(ActionItem.status == "done")

        query = query.order_by(ActionItem.created_at.desc()).limit(10)
        result = await session.execute(query)
        items = result.scalars().all()

        if not items:
            if filter_type == "overdue":
                return "Nothing overdue right now."
            return f"No {filter_type} action items found."

        # Filter by assignee name if provided (check entity metadata)
        if assignee_name:
            filtered = []
            for item in items:
                # Check the entity for assignee info
                ent_result = await session.execute(
                    select(Entity).where(Entity.id == item.entity_id)
                )
                ent = ent_result.scalar_one_or_none()
                if ent and assignee_name in (ent.metadata_json or {}).get("assignee_name", "").lower():
                    filtered.append(item)
            items = filtered
            if not items:
                return f"No action items found for {assignee_name}."

        lines = []
        for item in items[:5]:
            line = f"- {item.description[:80]}"
            if item.due_date:
                if item.due_date < date.today() and item.status != "done":
                    line += f" (OVERDUE, was due {item.due_date.strftime('%b %d')})"
                else:
                    line += f" (due {item.due_date.strftime('%b %d')})"
            line += f" [{item.status}]"
            lines.append(line)

        count_note = f" (showing 5 of {len(items)})" if len(items) > 5 else ""
        return f"Found {len(items)} action items{count_note}:\n" + "\n".join(lines)


async def _search_memory(tool_input: dict, org_id: str | None) -> str:
    """Search organizational memory — decisions, entities, summaries.

    Uses keyword-based search: breaks the query into individual words and
    matches any keyword against each field (OR logic within fields).
    """
    from gneva.db import async_session_factory
    from gneva.models.entity import Entity, Decision, ActionItem
    from gneva.models.meeting import MeetingSummary
    from sqlalchemy import select, or_, and_

    if not org_id:
        return "No organizational context available."

    query = tool_input.get("query", "").strip()
    if not query:
        return "No search query provided."

    org_uuid = uuid.UUID(org_id)
    results = []

    # Extract meaningful keywords (skip stop words)
    stop_words = {"the", "a", "an", "is", "was", "were", "with", "from", "for",
                  "and", "or", "in", "on", "at", "to", "of", "that", "this",
                  "it", "by", "about", "up", "can", "you", "me", "my", "we",
                  "our", "any", "all", "do", "did", "does", "has", "have", "had",
                  "be", "been", "being", "what", "when", "where", "how", "who",
                  "which", "there", "their", "they", "them", "today", "yesterday"}
    keywords = [w for w in query.lower().split() if w not in stop_words and len(w) > 1]
    if not keywords:
        keywords = query.lower().split()[:3]  # fallback: use first 3 words

    async with async_session_factory() as session:
        # Search decisions — match any keyword
        dec_filters = []
        for kw in keywords:
            escaped = _escape_like(kw)
            dec_filters.append(Decision.statement.ilike(f"%{escaped}%"))
            dec_filters.append(Decision.rationale.ilike(f"%{escaped}%"))
        dec_result = await session.execute(
            select(Decision).where(
                Decision.org_id == org_uuid,
                or_(*dec_filters),
            ).order_by(Decision.created_at.desc()).limit(3)
        )
        decisions = dec_result.scalars().all()
        for d in decisions:
            results.append(
                f"Decision ({d.created_at.strftime('%b %d')}): {d.statement[:100]} "
                f"[{d.status}]"
            )

        # Search entities — match any keyword
        ent_filters = []
        for kw in keywords:
            escaped = _escape_like(kw)
            ent_filters.append(Entity.name.ilike(f"%{escaped}%"))
            ent_filters.append(Entity.description.ilike(f"%{escaped}%"))
        ent_result = await session.execute(
            select(Entity).where(
                Entity.org_id == org_uuid,
                or_(*ent_filters),
            ).order_by(Entity.last_seen.desc()).limit(5)
        )
        entities = ent_result.scalars().all()
        for e in entities:
            desc = f": {e.description[:80]}" if e.description else ""
            results.append(f"{e.type.title()} - {e.name}{desc}")

        # Search meeting summaries — match any keyword
        from gneva.models.meeting import Meeting
        sum_filters = []
        for kw in keywords:
            escaped = _escape_like(kw)
            sum_filters.append(MeetingSummary.tldr.ilike(f"%{escaped}%"))
        sum_result = await session.execute(
            select(MeetingSummary)
            .join(Meeting, Meeting.id == MeetingSummary.meeting_id)
            .where(
                Meeting.org_id == org_uuid,
                or_(*sum_filters),
            ).order_by(MeetingSummary.created_at.desc()).limit(3)
        )
        summaries = sum_result.scalars().all()
        for s in summaries:
            results.append(
                f"Meeting summary ({s.created_at.strftime('%b %d')}): {s.tldr[:150]}"
            )

        # Search action items — match any keyword against description
        ai_filters = []
        for kw in keywords:
            escaped = _escape_like(kw)
            ai_filters.append(ActionItem.description.ilike(f"%{escaped}%"))
        ai_result = await session.execute(
            select(ActionItem).where(
                ActionItem.org_id == org_uuid,
                or_(*ai_filters),
            ).order_by(ActionItem.created_at.desc()).limit(3)
        )
        action_items = ai_result.scalars().all()
        for ai in action_items:
            due = f" (due {ai.due_date.strftime('%b %d')})" if ai.due_date else ""
            results.append(
                f"Action item{due}: {ai.description[:100]} [{ai.status}]"
            )

    if not results:
        return f"Nothing found in memory for '{query}'."

    return "From memory:\n" + "\n".join(f"- {r}" for r in results)


async def _bookmark_moment(
    tool_input: dict,
    org_id: str | None,
    meeting_id: str | None,
    transcript_buffer: list[dict] | None = None,
    meeting_start_time: float | None = None,
) -> str:
    """Bookmark the current moment in the meeting."""
    from gneva.db import async_session_factory
    from gneva.models.entity import GnevaMessage

    if not org_id or not meeting_id:
        return "Cannot bookmark without meeting context."

    label = tool_input.get("label", "").strip() or "Bookmarked moment"
    timestamp_sec = max(0, time.time() - meeting_start_time) if meeting_start_time else 0

    # Grab recent transcript for context
    context_lines = []
    if transcript_buffer:
        for seg in transcript_buffer[-5:]:
            context_lines.append(f"{seg['speaker']}: {seg['text']}")
    context = "\n".join(context_lines) if context_lines else "(no transcript context)"

    # Store as a GnevaMessage with channel="bookmark"
    async with async_session_factory() as session:
        msg = GnevaMessage(
            org_id=uuid.UUID(org_id),
            meeting_id=uuid.UUID(meeting_id),
            channel="bookmark",
            direction="system",
            content=label,
            metadata_json={
                "timestamp_sec": round(timestamp_sec),
                "transcript_context": context,
            },
        )
        session.add(msg)
        await session.commit()

    minutes = int(timestamp_sec // 60)
    return f"Bookmarked at {minutes} minutes in: '{label}'"


async def _describe_screen(screen_capture) -> str:
    """Get a fresh description of what's on screen."""
    if not screen_capture:
        return "Screen capture is not available in this meeting."

    # Force a fresh capture and analysis
    try:
        description = await screen_capture.capture_and_analyze_now()
        if description:
            return f"Currently on screen: {description}"
        return "I can see the meeting but nothing specific is being shared right now."
    except Exception as e:
        logger.warning(f"Screen describe failed: {e}")
        return "I couldn't get a clear look at the screen right now."


# ---------------------------------------------------------------------------
# External tools — web search, research, URL fetching
# ---------------------------------------------------------------------------

async def _brave_search(query: str, count: int = 5) -> list[dict]:
    """Search the web using Brave Search API. Returns list of {title, url, snippet}."""
    import aiohttp
    from gneva.config import get_settings
    settings = get_settings()

    if not settings.brave_search_api_key:
        return []

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": settings.brave_search_api_key,
                },
                params={"q": query, "count": str(count)},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Brave search returned {resp.status}")
                    return []
                data = await resp.json()
                results = []
                for item in (data.get("web", {}).get("results", []))[:count]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("description", ""),
                    })
                return results
    except Exception as e:
        logger.warning(f"Brave search failed: {e}")
        return []


def _is_url_safe(url: str) -> bool:
    """Check URL is not targeting internal/private networks (SSRF protection)."""
    import ipaddress
    import socket
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False

        # Block cloud metadata endpoints
        _blocked_hosts = {
            "169.254.169.254", "metadata.google.internal",
            "metadata.internal", "100.100.100.200",
        }
        if hostname in _blocked_hosts:
            return False

        # Block localhost
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False

        # Resolve hostname and check for private IPs
        try:
            resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for _, _, _, _, sockaddr in resolved:
                ip = ipaddress.ip_address(sockaddr[0])
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    return False
        except socket.gaierror:
            return False  # Can't resolve = don't fetch

        return True
    except Exception:
        return False


async def _fetch_page_text(url: str, max_chars: int = 3000) -> str:
    """Fetch a URL and extract readable text content."""
    import aiohttp
    import re

    # Basic URL validation
    if not url.startswith(("http://", "https://")):
        return "Invalid URL — must start with http:// or https://"

    # SSRF protection — block internal/private network URLs
    if not _is_url_safe(url):
        return "Cannot fetch this URL — it points to an internal or private network address."

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={"User-Agent": "Gneva/1.0 (Meeting AI Assistant)"},
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    return f"Could not fetch URL (HTTP {resp.status})"
                content_type = resp.headers.get("Content-Type", "")
                if "text/html" not in content_type and "text/plain" not in content_type:
                    return f"URL returned non-text content ({content_type})"

                html = await resp.text()

                # Strip HTML tags for a rough text extraction
                # Remove script and style blocks first
                text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
                text = re.sub(r'<[^>]+>', ' ', text)
                # Clean up whitespace
                text = re.sub(r'\s+', ' ', text).strip()

                if len(text) > max_chars:
                    text = text[:max_chars] + "..."

                return text if text else "Page was empty or could not be parsed."
    except asyncio.TimeoutError:
        return "URL fetch timed out after 15 seconds."
    except Exception as e:
        return f"Failed to fetch URL: {e}"


async def _web_search(tool_input: dict) -> str:
    """Search the web and return summarized results."""
    query = tool_input.get("query", "").strip()
    if not query:
        return "No search query provided."

    # Try Brave Search first
    results = await _brave_search(query)

    if results:
        lines = []
        for r in results:
            lines.append(f"- {r['title']}: {r['snippet']}")
            lines.append(f"  ({r['url']})")
        return f"Search results for '{query}':\n" + "\n".join(lines)

    # Fallback: use Claude's knowledge (no external API needed)
    try:
        from gneva.services import get_anthropic_client
        client = get_anthropic_client()

        response = await asyncio.to_thread(
            client.messages.create,
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": (
                    f"Answer this question concisely (3-5 bullet points max): {query}\n\n"
                    "Be factual. If you're not sure, say so. Include specific numbers, "
                    "dates, and names when possible."
                ),
            }],
        )
        answer = response.content[0].text.strip()
        return f"Based on my knowledge (no live web results available):\n{answer}"
    except Exception as e:
        logger.warning(f"Knowledge fallback failed: {e}")
        return "Web search is not configured and I couldn't look this up. You may need to set a BRAVE_SEARCH_API_KEY."


async def _quick_research(tool_input: dict) -> str:
    """Do a deeper research pass — search, fetch top results, synthesize."""
    topic = tool_input.get("topic", "").strip()
    context = tool_input.get("context", "").strip()
    if not topic:
        return "No research topic provided."

    # Step 1: Search
    results = await _brave_search(topic, count=3)

    # Step 2: Fetch top 2 pages for more detail
    page_contents = []
    for r in results[:2]:
        text = await _fetch_page_text(r["url"], max_chars=2000)
        if text and "Could not fetch" not in text and "timed out" not in text:
            page_contents.append(f"From {r['title']}:\n{text[:1500]}")

    # Step 3: Synthesize with Claude
    try:
        from gneva.services import get_anthropic_client
        client = get_anthropic_client()

        source_material = ""
        if page_contents:
            source_material = "\n\n---\n\n".join(page_contents)
        elif results:
            source_material = "\n".join(
                f"- {r['title']}: {r['snippet']}" for r in results
            )

        synthesis_prompt = f"Research topic: {topic}"
        if context:
            synthesis_prompt += f"\nAdditional context: {context}"
        if source_material:
            synthesis_prompt += f"\n\nSource material:\n{source_material}"

        response = await asyncio.to_thread(
            client.messages.create,
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=(
                "You are a research assistant. Synthesize the provided information "
                "into a concise briefing (5-8 bullet points). Be specific with numbers, "
                "dates, and facts. Note if information might be outdated. If sources "
                "contradict each other, mention that."
            ),
            messages=[{"role": "user", "content": synthesis_prompt}],
        )
        return response.content[0].text.strip()

    except Exception as e:
        logger.warning(f"Research synthesis failed: {e}")
        # Return raw search results as fallback
        if results:
            lines = [f"- {r['title']}: {r['snippet']}" for r in results]
            return f"Raw search results (synthesis failed):\n" + "\n".join(lines)
        return f"Research failed: {e}"


async def _fetch_url(tool_input: dict) -> str:
    """Fetch a URL and summarize its content."""
    url = tool_input.get("url", "").strip()
    if not url:
        return "No URL provided."

    text = await _fetch_page_text(url, max_chars=4000)

    if not text or "Could not fetch" in text or "timed out" in text or "Failed" in text:
        return text

    # Summarize with Claude if content is long
    if len(text) > 500:
        try:
            from gneva.services import get_anthropic_client
            client = get_anthropic_client()

            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Summarize this web page content in 3-5 concise bullet points. "
                        f"Focus on the key information:\n\n{text}"
                    ),
                }],
            )
            return f"Summary of {url}:\n{response.content[0].text.strip()}"
        except Exception:
            pass

    return f"Content from {url}:\n{text[:1000]}"


# ---------------------------------------------------------------------------
# Multi-agent orchestrator tool executors
# ---------------------------------------------------------------------------

async def _summon_agent(tool_input: dict, agent_router) -> str:
    """Summon a specialist agent into the meeting."""
    if not agent_router:
        return "Multi-agent system is not available in this meeting."

    agent_name = tool_input.get("agent_name", "").strip().lower()
    reason = tool_input.get("reason", "").strip()
    if not agent_name:
        return "No agent name specified."

    result = await agent_router.summon_agent(agent_name, reason)
    if result["success"]:
        return f"{result['display_name']} has joined the meeting. {result.get('message', '')}"
    return result.get("message", f"Could not summon {agent_name}.")


async def _dismiss_agent(tool_input: dict, agent_router) -> str:
    """Dismiss a specialist agent from the meeting."""
    if not agent_router:
        return "Multi-agent system is not available in this meeting."

    agent_name = tool_input.get("agent_name", "").strip().lower()
    if not agent_name:
        return "No agent name specified."

    result = await agent_router.dismiss_agent(agent_name)
    return result.get("message", "Done.")


async def _ask_agent(tool_input: dict, agent_router, transcript_buffer) -> str:
    """Privately ask a specialist agent a question."""
    if not agent_router:
        return "Multi-agent system is not available in this meeting."

    agent_name = tool_input.get("agent_name", "").strip().lower()
    question = tool_input.get("question", "").strip()
    if not agent_name or not question:
        return "Need both agent_name and question."

    result = await agent_router.ask_agent(agent_name, question, transcript_buffer=transcript_buffer)
    confidence = result.get("confidence", 0)
    response = result.get("response", "No response.")
    conf_note = f" (confidence: {confidence:.0%})" if confidence < 0.7 else ""
    return f"{agent_name}'s input{conf_note}: {response}"


async def _delegate_question(tool_input: dict, agent_router, transcript_buffer) -> str:
    """Delegate a question to a specialist who speaks publicly."""
    if not agent_router:
        return "Multi-agent system is not available in this meeting."

    agent_name = tool_input.get("agent_name", "").strip().lower()
    question = tool_input.get("question", "").strip()
    if not agent_name or not question:
        return "Need both agent_name and question."

    # Summon if not already active
    await agent_router.summon_agent(agent_name, question, mode="active")

    result = await agent_router.ask_agent(agent_name, question, transcript_buffer=transcript_buffer)
    display_name = agent_router._profiles.get(agent_name, {}).get("display_name", agent_name)
    response = result.get("response", "")
    if not response:
        return f"{display_name} didn't have a response ready."

    # Mark this as a public response — the conversation engine will speak it
    return f"[{display_name}]: {response}"


async def _request_deliberation(tool_input: dict, agent_router, transcript_buffer) -> str:
    """Request multi-agent deliberation on a question."""
    if not agent_router:
        return "Multi-agent system is not available in this meeting."

    question = tool_input.get("question", "").strip()
    agent_names = tool_input.get("agent_names", [])
    if not question or not agent_names:
        return "Need both a question and a list of agent names."
    if len(agent_names) > 5:
        agent_names = agent_names[:5]

    result = await agent_router.request_deliberation(
        question=question,
        agent_names=agent_names,
        transcript_buffer=transcript_buffer,
    )

    synthesis = result.get("synthesis", "")
    time_taken = result.get("time_taken", 0)
    n_opinions = len(result.get("opinions", []))

    return f"Deliberation result ({n_opinions} agents, {time_taken}s): {synthesis}"


async def _meeting_pulse(agent_router) -> str:
    """Get current meeting agent stats."""
    if not agent_router:
        return "Multi-agent system is not available in this meeting."

    stats = await agent_router.get_stats()
    agents = stats.get("active_agents", [])

    if not agents:
        return "No agents currently active."

    lines = []
    for a in agents:
        mode_tag = f" ({a['mode']})" if a['mode'] != 'active' else ""
        spoke_tag = f", spoken {a['times_spoken']}x" if a['times_spoken'] else ""
        lines.append(f"- {a['display_name']}{mode_tag}{spoke_tag}")

    return f"Active agents:\n" + "\n".join(lines) + f"\nTotal inter-agent messages: {stats['total_messages']}"


async def _generate_briefing(tool_input: dict, org_id: str | None,
                              meeting_id: str | None,
                              transcript_buffer: list[dict] | None) -> str:
    """Generate a pre-meeting briefing from organizational memory."""
    if not org_id:
        return "Cannot generate briefing without organization context."

    from gneva.db import async_session_factory
    from gneva.models.entity import ActionItem, Decision
    from gneva.models.meeting import MeetingSummary
    from sqlalchemy import select

    org_uuid = uuid.UUID(org_id)
    focus = tool_input.get("focus_topics", "").strip()

    briefing_parts = []

    async with async_session_factory() as session:
        # Open action items
        items_result = await session.execute(
            select(ActionItem)
            .where(ActionItem.org_id == org_uuid, ActionItem.status.in_(["open", "in_progress"]))
            .order_by(ActionItem.created_at.desc())
            .limit(8)
        )
        items = items_result.scalars().all()
        if items:
            item_lines = []
            for it in items:
                overdue = ""
                if it.due_date and it.due_date < date.today():
                    overdue = " OVERDUE"
                item_lines.append(f"  - {it.description[:80]} [{it.status}]{overdue}")
            briefing_parts.append("Open action items:\n" + "\n".join(item_lines))

        # Recent decisions
        dec_result = await session.execute(
            select(Decision)
            .where(Decision.org_id == org_uuid)
            .order_by(Decision.created_at.desc())
            .limit(5)
        )
        decisions = dec_result.scalars().all()
        if decisions:
            dec_lines = [f"  - {d.statement[:80]} ({d.created_at.strftime('%b %d')})" for d in decisions]
            briefing_parts.append("Recent decisions:\n" + "\n".join(dec_lines))

        # Last meeting summary (scoped to org)
        from gneva.models.meeting import Meeting
        sum_result = await session.execute(
            select(MeetingSummary)
            .join(Meeting, Meeting.id == MeetingSummary.meeting_id)
            .where(Meeting.org_id == org_uuid)
            .order_by(MeetingSummary.created_at.desc())
            .limit(1)
        )
        summary = sum_result.scalar_one_or_none()
        if summary:
            briefing_parts.append(f"Last meeting ({summary.created_at.strftime('%b %d')}): {summary.tldr[:200]}")

    if not briefing_parts:
        return "No previous meeting data found for a briefing."

    # Synthesize with Claude
    try:
        from gneva.services import get_anthropic_client
        client = get_anthropic_client()

        raw_briefing = "\n\n".join(briefing_parts)
        focus_note = f"\nFocus areas requested: {focus}" if focus else ""

        response = await asyncio.to_thread(
            client.messages.create,
            model="claude-haiku-4-5-20251001",
            max_tokens=250,
            system=(
                "You are preparing a brief verbal meeting briefing. Summarize the key points "
                "in 3-5 spoken sentences. Be concise — this will be read aloud. "
                "Prioritize overdue items and recent decisions. No markdown."
            ),
            messages=[{
                "role": "user",
                "content": f"Generate a briefing from this data:\n{raw_briefing}{focus_note}",
            }],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning(f"Briefing synthesis failed: {e}")
        return "\n\n".join(briefing_parts)


async def _close_meeting_summary(tool_input: dict, org_id: str | None,
                                  meeting_id: str | None,
                                  transcript_buffer: list[dict] | None,
                                  meeting_start_time: float | None,
                                  agent_router) -> str:
    """Generate end-of-meeting summary from the full transcript."""
    if not transcript_buffer:
        return "No transcript available to summarize."

    additional_notes = tool_input.get("additional_notes", "").strip()

    # Build full transcript
    transcript_text = "\n".join(
        f"{seg['speaker']}: {seg['text']}" for seg in transcript_buffer
    )
    if len(transcript_text) > 8000:
        transcript_text = transcript_text[-8000:]  # last ~8k chars

    # Duration
    duration_min = int((time.time() - (meeting_start_time or time.time())) / 60)

    # Agent stats
    agent_info = ""
    if agent_router:
        stats = await agent_router.get_stats()
        active = stats.get("active_agents", [])
        if active:
            agent_info = f"\nAgents that participated: {', '.join(a['display_name'] for a in active)}"
            agent_info += f"\nInter-agent messages: {stats['total_messages']}"

    try:
        from gneva.services import get_anthropic_client
        client = get_anthropic_client()

        response = await asyncio.to_thread(
            client.messages.create,
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=(
                "You are generating a spoken end-of-meeting summary. Structure as:\n"
                "1. One-sentence TLDR\n"
                "2. Key decisions made (if any)\n"
                "3. Action items assigned (if any)\n"
                "4. Open questions or unresolved items\n"
                "5. Suggested next steps\n\n"
                "Keep it concise — this will be spoken aloud. Use natural language, "
                "no markdown or bullet points. 4-8 sentences max."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Meeting duration: {duration_min} minutes\n"
                    f"{agent_info}\n"
                    f"{'Additional notes: ' + additional_notes if additional_notes else ''}\n\n"
                    f"Full transcript:\n{transcript_text}\n\n"
                    "Generate the meeting summary."
                ),
            }],
        )
        summary_text = response.content[0].text.strip()

        # Persist summary to database
        if org_id and meeting_id:
            try:
                from gneva.db import async_session_factory
                from gneva.models.meeting import MeetingSummary

                async with async_session_factory() as session:
                    ms = MeetingSummary(
                        meeting_id=uuid.UUID(meeting_id),
                        tldr=summary_text[:500],
                        full_summary=summary_text,
                    )
                    session.add(ms)
                    await session.commit()
                    logger.info(f"Meeting summary persisted for {meeting_id}")
            except Exception as e:
                logger.warning(f"Failed to persist meeting summary: {e}")

        return summary_text

    except Exception as e:
        logger.error(f"Meeting summary generation failed: {e}")
        return f"I couldn't generate a summary right now: {e}"
