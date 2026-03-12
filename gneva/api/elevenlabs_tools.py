"""ElevenLabs ConvAI server tool webhooks.

These endpoints are called by the ElevenLabs agent when it decides to use a tool.
They bridge the ElevenLabs agent to our backend's memory, agents, and action items.
"""

import logging
import uuid

from fastapi import APIRouter, Request
from sqlalchemy import text

from gneva.db import async_session_factory
from gneva.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/el-tools", tags=["elevenlabs-tools"])
settings = get_settings()

# Global registry for active screen capture engines (meeting_id -> ScreenCaptureEngine)
_active_screen_captures: dict[str, "ScreenCaptureEngine"] = {}


def register_screen_capture(meeting_id: str, engine):
    """Register an active screen capture engine for a meeting."""
    _active_screen_captures[meeting_id] = engine
    logger.info(f"Screen capture registered for meeting {meeting_id}")


def unregister_screen_capture(meeting_id: str):
    """Remove a screen capture engine when the meeting ends."""
    _active_screen_captures.pop(meeting_id, None)


@router.post("/search-memory")
async def tool_search_memory(request: Request):
    """Search organizational memory (entities, decisions, past discussions)."""
    body = await request.json()
    query = body.get("query", "")
    if not query:
        return {"result": "No query provided."}

    logger.info(f"EL tool: search_memory query='{query}'")

    try:
        async with async_session_factory() as db:
            # Search entities by name/description
            rows = await db.execute(
                text("""
                    SELECT name, type, description, mention_count
                    FROM entities
                    WHERE name ILIKE :q OR description ILIKE :q
                    ORDER BY mention_count DESC
                    LIMIT 10
                """),
                {"q": f"%{query}%"},
            )
            entities = [dict(r._mapping) for r in rows]

            # Search decisions
            dec_rows = await db.execute(
                text("""
                    SELECT statement, rationale, status, decided_at
                    FROM decisions
                    WHERE statement ILIKE :q OR rationale ILIKE :q
                    ORDER BY decided_at DESC
                    LIMIT 5
                """),
                {"q": f"%{query}%"},
            )
            decisions = [dict(r._mapping) for r in dec_rows]

            if not entities and not decisions:
                return {"result": f"No memory found for '{query}'."}

            parts = []
            if entities:
                parts.append("**Entities:**")
                for e in entities:
                    parts.append(f"- {e['name']} ({e['type']}): {e['description'] or 'no description'} (mentioned {e['mention_count']}x)")
            if decisions:
                parts.append("\n**Decisions:**")
                for d in decisions:
                    parts.append(f"- {d['statement']} — Rationale: {d['rationale'] or 'none'} (Status: {d['status']})")

            return {"result": "\n".join(parts)}

    except Exception as e:
        logger.error(f"search_memory error: {e}")
        return {"result": "Memory search failed. Please try again."}


@router.post("/create-action-item")
async def tool_create_action_item(request: Request):
    """Create an action item from the meeting."""
    body = await request.json()
    description = body.get("description", "")
    assignee = body.get("assignee_name", "")
    due_date = body.get("due_date", "")
    priority = body.get("priority", "medium")

    if not description:
        return {"result": "No description provided."}

    logger.info(f"EL tool: create_action_item desc='{description[:60]}' assignee='{assignee}'")

    try:
        async with async_session_factory() as db:
            item_id = str(uuid.uuid4())
            await db.execute(
                text("""
                    INSERT INTO action_items (id, description, assignee_name, due_date, priority, status, created_at)
                    VALUES (:id, :desc, :assignee, :due, :priority, 'open', NOW())
                """),
                {
                    "id": item_id,
                    "desc": description,
                    "assignee": assignee or None,
                    "due": due_date or None,
                    "priority": priority,
                },
            )
            await db.commit()

            result = f"Action item created: '{description}'"
            if assignee:
                result += f" assigned to {assignee}"
            if due_date:
                result += f" due {due_date}"
            return {"result": result}

    except Exception as e:
        logger.error(f"create_action_item error: {e}")
        return {"result": "Failed to create action item. Please try again."}


@router.post("/query-action-items")
async def tool_query_action_items(request: Request):
    """Query existing action items."""
    body = await request.json()
    filter_type = body.get("filter", "open")
    assignee = body.get("assignee_name", "")

    logger.info(f"EL tool: query_action_items filter={filter_type} assignee={assignee}")

    try:
        async with async_session_factory() as db:
            q = "SELECT description, assignee_name, priority, status, due_date FROM action_items"
            params = {}

            conditions = []
            if filter_type == "open":
                conditions.append("status IN ('open', 'in_progress')")
            elif filter_type == "done":
                conditions.append("status = 'done'")
            elif filter_type == "overdue":
                conditions.append("status != 'done' AND due_date < NOW()")

            if assignee:
                conditions.append("assignee_name ILIKE :assignee")
                params["assignee"] = f"%{assignee}%"

            if conditions:
                q += " WHERE " + " AND ".join(conditions)
            q += " ORDER BY created_at DESC LIMIT 20"

            rows = await db.execute(text(q), params)
            items = [dict(r._mapping) for r in rows]

            if not items:
                return {"result": f"No {filter_type} action items found."}

            parts = [f"**{len(items)} {filter_type} action items:**"]
            for i in items:
                line = f"- [{i['priority']}] {i['description']}"
                if i['assignee_name']:
                    line += f" → {i['assignee_name']}"
                if i['due_date']:
                    line += f" (due {i['due_date']})"
                line += f" [{i['status']}]"
                parts.append(line)

            return {"result": "\n".join(parts)}

    except Exception as e:
        logger.error(f"query_action_items error: {e}")
        return {"result": "Failed to query action items. Please try again."}


@router.post("/web-search")
async def tool_web_search(request: Request):
    """Search the web using Brave Search API."""
    body = await request.json()
    query = body.get("query", "")
    if not query:
        return {"result": "No search query provided."}

    logger.info(f"EL tool: web_search query='{query}'")

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"Accept": "application/json", "X-Subscription-Token": settings.brave_api_key},
                params={"q": query, "count": 5},
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("web", {}).get("results", [])
        if not results:
            return {"result": f"No web results for '{query}'."}

        parts = [f"**Web search results for '{query}':**"]
        for r in results[:5]:
            parts.append(f"- **{r['title']}**: {r.get('description', 'No description')}")
            parts.append(f"  URL: {r['url']}")

        return {"result": "\n".join(parts)}

    except Exception as e:
        logger.error(f"web_search error: {e}")
        return {"result": "Web search failed. Please try again."}


@router.post("/ask-agent")
async def tool_ask_agent(request: Request):
    """Route a question to one of the 16 specialist agents."""
    body = await request.json()
    agent_name = body.get("agent_name", "").lower()
    question = body.get("question", "")

    if not agent_name or not question:
        return {"result": "Need both agent_name and question."}

    logger.info(f"EL tool: ask_agent agent={agent_name} q='{question[:60]}'")

    try:
        from gneva.bot.agent_router import AgentRouter

        router_instance = AgentRouter(meeting_id="elevenlabs-session")
        await router_instance.initialize()

        result = await router_instance.ask_agent(
            agent_name=agent_name,
            question=question,
            context="Asked via ElevenLabs voice agent in a Teams meeting.",
        )

        if result.get("success") is False:
            return {"result": result.get("message", "Agent not available.")}

        response = result.get("response", "No response.")
        agent_display = result.get("display_name", agent_name)
        return {"result": f"**{agent_display}**: {response}"}

    except Exception as e:
        logger.error(f"ask_agent error: {e}")
        return {"result": "Agent query failed. Please try again."}


@router.post("/describe-screen")
async def tool_describe_screen(request: Request):
    """Describe what's currently on screen using the browser bot's visual awareness."""
    body = await request.json()
    meeting_id = body.get("meeting_id", "")

    logger.info(f"EL tool: describe_screen meeting_id='{meeting_id}'")

    # Try to find an active screen capture engine
    engine = None
    if meeting_id and meeting_id in _active_screen_captures:
        engine = _active_screen_captures[meeting_id]
    elif _active_screen_captures:
        # If no meeting_id or not found, use the first active one
        engine = next(iter(_active_screen_captures.values()))

    if not engine:
        return {"result": "No visual feed available — browser bot is not connected to a meeting right now."}

    try:
        description = await engine.describe_now()
        return {"result": description}
    except Exception as e:
        logger.error(f"describe_screen error: {e}")
        return {"result": "Screen capture failed. Please try again."}


@router.post("/list-agents")
async def tool_list_agents(request: Request):
    """List available specialist agents and their roles."""
    from gneva.bot.agent_router import AGENT_PROFILES

    parts = ["**Available specialist agents:**"]
    for name, profile in AGENT_PROFILES.items():
        parts.append(f"- **{profile['display_name']}** ({name}): {profile['role']}")

    return {"result": "\n".join(parts)}
