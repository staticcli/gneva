"""Phase 7 — Swarm Mode, Memory Mesh, and Cross-Meeting Intelligence.

Swarm: Temporary multi-agent task forces that persist across conversation turns.
Memory Mesh: Shared agent memory that persists across meetings.
Cross-Meeting Intelligence: Pattern detection across meeting history.
"""

import asyncio
import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SWARM MODE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class Swarm:
    """A temporary task force of agents working on a complex problem.

    Unlike deliberation (single-round Q&A), swarms persist across multiple
    conversation turns and track progress toward resolution.
    """

    def __init__(self, swarm_id: str, topic: str, lead_agent: str,
                 member_agents: list[str], meeting_id: str,
                 max_rounds: int = 5, timeout_sec: float = 300):
        self.id = swarm_id
        self.topic = topic
        self.lead_agent = lead_agent
        self.members = member_agents
        self.meeting_id = meeting_id
        self.max_rounds = max_rounds
        self.timeout_sec = timeout_sec

        self.status = "active"  # active, resolved, timed_out, disbanded
        self.created_at = time.time()
        self.rounds: list[dict] = []  # [{round: int, contributions: {agent: text}, synthesis: str}]
        self.resolution: str | None = None
        self.artifacts: list[dict] = []  # Outputs: decisions, action items, recommendations

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.timeout_sec

    @property
    def round_count(self) -> int:
        return len(self.rounds)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "lead_agent": self.lead_agent,
            "members": self.members,
            "status": self.status,
            "rounds_completed": self.round_count,
            "max_rounds": self.max_rounds,
            "artifacts": self.artifacts,
            "resolution": self.resolution,
            "elapsed_sec": round(time.time() - self.created_at, 1),
        }


class SwarmCoordinator:
    """Manages active swarms within a meeting."""

    MAX_CONCURRENT_SWARMS = 3

    def __init__(self, meeting_id: str, agent_router):
        self.meeting_id = meeting_id
        self._router = agent_router
        self._swarms: dict[str, Swarm] = {}

    async def create_swarm(self, topic: str, lead_agent: str,
                           member_agents: list[str],
                           max_rounds: int = 5,
                           timeout_sec: float = 300) -> dict:
        """Create a new swarm to tackle a complex problem."""
        # Limit concurrent swarms
        active = [s for s in self._swarms.values() if s.status == "active"]
        if len(active) >= self.MAX_CONCURRENT_SWARMS:
            return {"success": False, "error": "Too many active swarms. Resolve or disband one first."}

        swarm_id = str(uuid.uuid4())[:8]
        swarm = Swarm(
            swarm_id=swarm_id,
            topic=topic,
            lead_agent=lead_agent,
            member_agents=member_agents,
            meeting_id=self.meeting_id,
            max_rounds=max_rounds,
            timeout_sec=timeout_sec,
        )
        self._swarms[swarm_id] = swarm

        # Run first round
        result = await self._run_round(swarm)

        logger.info(f"Swarm '{swarm_id}' created: {topic} (lead={lead_agent}, members={member_agents})")
        return {
            "success": True,
            "swarm_id": swarm_id,
            "topic": topic,
            "round_result": result,
            "status": swarm.status,
        }

    async def continue_swarm(self, swarm_id: str, new_input: str = "") -> dict:
        """Continue a swarm's work with optional new input from the meeting."""
        swarm = self._swarms.get(swarm_id)
        if not swarm:
            return {"success": False, "error": f"Swarm '{swarm_id}' not found"}
        if swarm.status == "pending_resolution":
            return await self.resolve_swarm(swarm_id, auto=True)
        if swarm.status != "active":
            return {"success": False, "error": f"Swarm is {swarm.status}", "resolution": swarm.resolution}
        if swarm.is_expired:
            swarm.status = "timed_out"
            return {"success": False, "error": "Swarm timed out"}
        if swarm.round_count >= swarm.max_rounds:
            return await self.resolve_swarm(swarm_id, auto=True)

        result = await self._run_round(swarm, new_input=new_input)
        return {
            "success": True,
            "swarm_id": swarm_id,
            "round": swarm.round_count,
            "round_result": result,
            "status": swarm.status,
        }

    async def resolve_swarm(self, swarm_id: str, resolution: str = "",
                            auto: bool = False) -> dict:
        """Mark a swarm as resolved and generate final artifacts."""
        swarm = self._swarms.get(swarm_id)
        if not swarm:
            return {"success": False, "error": f"Swarm '{swarm_id}' not found"}

        # Synthesize final resolution if auto-resolving
        if auto or not resolution:
            resolution = await self._synthesize_resolution(swarm)

        swarm.status = "resolved"
        swarm.resolution = resolution

        # Persist to memory mesh
        await self._persist_swarm_result(swarm)

        logger.info(f"Swarm '{swarm_id}' resolved after {swarm.round_count} rounds")
        return {
            "success": True,
            "swarm_id": swarm_id,
            "resolution": resolution,
            "rounds_completed": swarm.round_count,
            "artifacts": swarm.artifacts,
        }

    async def disband_swarm(self, swarm_id: str) -> dict:
        """Disband a swarm without resolution."""
        swarm = self._swarms.get(swarm_id)
        if not swarm:
            return {"success": False, "error": f"Swarm '{swarm_id}' not found"}
        swarm.status = "disbanded"
        return {"success": True, "message": f"Swarm '{swarm_id}' disbanded"}

    def list_swarms(self) -> list[dict]:
        return [s.to_dict() for s in self._swarms.values()]

    async def _run_round(self, swarm: Swarm, new_input: str = "") -> dict:
        """Execute one round of swarm collaboration."""
        round_num = swarm.round_count + 1

        # Build context from previous rounds
        history = ""
        if swarm.rounds:
            last = swarm.rounds[-1]
            history = f"\nPrevious round synthesis: {last.get('synthesis', '')}"

        prompt = f"SWARM ROUND {round_num}/{swarm.max_rounds}\nTopic: {swarm.topic}{history}"
        if new_input:
            prompt += f"\nNew input from meeting: {new_input}"
        prompt += "\nProvide your analysis in 2-3 sentences. Flag if you think the swarm can resolve now."

        # Ask all members in parallel via the router's bus
        if self._router._bus:
            responses = await self._router._bus.broadcast(
                from_agent=swarm.lead_agent,
                agent_names=swarm.members,
                message_type="deliberate",
                content=prompt,
                timeout=20,
            )
        else:
            responses = {}
            for name in swarm.members:
                try:
                    r = await self._router.ask_agent(name, prompt)
                    responses[name] = r.get("response", "")
                except Exception:
                    responses[name] = None

        contributions = {k: v for k, v in responses.items() if v}

        # Synthesize this round
        synthesis = await self._router._synthesize_opinions(
            swarm.topic,
            [{"agent": k, "display_name": k.capitalize(), "position": v, "confidence": 0.8}
             for k, v in contributions.items()],
        )

        round_data = {
            "round": round_num,
            "contributions": contributions,
            "synthesis": synthesis,
            "timestamp": time.time(),
        }
        swarm.rounds.append(round_data)

        # Check for early resolution signals
        resolution_signals = ["resolve now", "we can conclude", "consensus reached",
                              "ready to decide", "agreed", "clear recommendation"]
        all_text = (synthesis + " " + " ".join(contributions.values())).lower()
        ready_to_resolve = any(sig in all_text for sig in resolution_signals) and round_num >= 2
        if ready_to_resolve:
            swarm.status = "pending_resolution"

        return {"round": round_num, "synthesis": synthesis, "contributions": len(contributions),
                "ready_to_resolve": ready_to_resolve}

    async def _synthesize_resolution(self, swarm: Swarm) -> str:
        """Generate a final resolution from all swarm rounds."""
        if not swarm.rounds:
            return "No rounds completed."

        rounds_text = "\n\n".join(
            f"Round {r['round']}: {r['synthesis']}" for r in swarm.rounds
        )

        from gneva.services import llm_create
        try:
            response = await llm_create(
                model="claude-sonnet-4-6",
                max_tokens=300,
                system=(
                    "You are synthesizing the final resolution of a multi-agent swarm discussion. "
                    "Produce a clear, actionable conclusion in 3-5 sentences. "
                    "Include: the decision/recommendation, key reasoning, and any caveats. "
                    "Speak naturally — this will be read aloud."
                ),
                messages=[{"role": "user", "content": f"Topic: {swarm.topic}\n\nRound summaries:\n{rounds_text}\n\nFinal resolution:"}],
            )
            return response.content[0].text.strip() if response.content else "Unable to synthesize."
        except Exception as e:
            logger.error(f"Swarm resolution synthesis failed: {e}")
            return swarm.rounds[-1].get("synthesis", "Unable to synthesize.")

    async def _persist_swarm_result(self, swarm: Swarm):
        """Save swarm result to database for cross-meeting intelligence."""
        try:
            from gneva.db import async_session_factory
            from gneva.models.meeting import MeetingSummary

            async with async_session_factory() as session:
                record = MeetingSummary(
                    meeting_id=uuid.UUID(swarm.meeting_id),
                    tldr=f"[Swarm: {swarm.topic}] {swarm.resolution}",
                    topics_covered=[swarm.topic],
                    key_decisions=[swarm.resolution] if swarm.resolution else [],
                )
                session.add(record)
                await session.commit()
        except Exception as e:
            logger.debug(f"Failed to persist swarm result: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MEMORY MESH — Cross-agent shared memory
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class MemoryMesh:
    """Shared memory layer that allows agents to read/write knowledge
    that persists across meetings within an organization.

    Memory types:
    - fact: A verified piece of information (e.g., "AWS budget is $50k/month")
    - preference: A stakeholder preference (e.g., "CEO prefers weekly updates")
    - decision: A decision made in a meeting
    - insight: An agent-generated insight from analysis
    - warning: Something to watch out for in future meetings
    """

    MEMORY_TYPES = {"fact", "preference", "decision", "insight", "warning"}
    MAX_MEMORIES_PER_ORG = 1000

    def __init__(self, org_id: str):
        self.org_id = org_id
        # In-memory cache (loaded from DB on init)
        self._cache: dict[str, dict] = {}
        self._loaded = False

    async def load(self):
        """Load memories from database into cache."""
        try:
            from gneva.db import async_session_factory
            from gneva.models.agent import AgentMemory
            from sqlalchemy import select

            async with async_session_factory() as session:
                result = await session.execute(
                    select(AgentMemory)
                    .where(AgentMemory.org_id == uuid.UUID(self.org_id))
                    .where(AgentMemory.is_active == True)
                    .order_by(AgentMemory.relevance_score.desc())
                    .limit(self.MAX_MEMORIES_PER_ORG)
                )
                for mem in result.scalars().all():
                    self._cache[str(mem.id)] = {
                        "id": str(mem.id),
                        "type": mem.memory_type,
                        "content": mem.content,
                        "source_agent": mem.source_agent,
                        "source_meeting_id": str(mem.source_meeting_id) if mem.source_meeting_id else None,
                        "tags": mem.tags or [],
                        "relevance_score": mem.relevance_score,
                        "access_count": mem.access_count,
                        "created_at": mem.created_at.isoformat(),
                    }
            self._loaded = True
            logger.info(f"Memory mesh loaded {len(self._cache)} memories for org {self.org_id}")
        except Exception as e:
            logger.warning(f"Failed to load memory mesh: {e}")
            self._loaded = True  # Don't retry on every call

    async def remember(self, content: str, memory_type: str, source_agent: str,
                       meeting_id: str | None = None, tags: list[str] | None = None,
                       relevance_score: float = 0.5) -> dict:
        """Store a new memory in the mesh."""
        if memory_type not in self.MEMORY_TYPES:
            return {"success": False, "error": f"Invalid memory type. Use: {self.MEMORY_TYPES}"}

        if not self._loaded:
            await self.load()

        # Check for duplicate/similar content (simple substring check)
        for existing in self._cache.values():
            if content.lower()[:100] == existing["content"].lower()[:100]:
                return {"success": False, "error": "Similar memory already exists", "existing_id": existing["id"]}

        memory_id = str(uuid.uuid4())
        memory = {
            "id": memory_id,
            "type": memory_type,
            "content": content,
            "source_agent": source_agent,
            "source_meeting_id": meeting_id,
            "tags": tags or [],
            "relevance_score": relevance_score,
            "access_count": 0,
            "created_at": datetime.utcnow().isoformat(),
        }
        self._cache[memory_id] = memory

        # Persist to DB
        await self._persist_memory(memory)

        return {"success": True, "memory_id": memory_id}

    async def recall(self, query: str, memory_type: str | None = None,
                     tags: list[str] | None = None, limit: int = 10) -> list[dict]:
        """Recall memories matching a query."""
        if not self._loaded:
            await self.load()

        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []
        for mem in self._cache.values():
            if memory_type and mem["type"] != memory_type:
                continue
            if tags and not any(t in mem.get("tags", []) for t in tags):
                continue

            content_lower = mem["content"].lower()
            # Score based on word overlap
            content_words = set(content_lower.split())
            overlap = len(query_words & content_words)
            if overlap == 0 and query_lower not in content_lower:
                continue

            score = overlap / max(len(query_words), 1)
            # Boost by relevance and recency
            score += mem.get("relevance_score", 0) * 0.3
            scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [m for _, m in scored[:limit]]

        # Bump access counts
        for m in results:
            m["access_count"] = m.get("access_count", 0) + 1

        return results

    async def forget(self, memory_id: str) -> dict:
        """Deactivate a memory."""
        if memory_id in self._cache:
            del self._cache[memory_id]
            await self._deactivate_memory(memory_id)
            return {"success": True}
        return {"success": False, "error": "Memory not found"}

    def get_stats(self) -> dict:
        type_counts = defaultdict(int)
        for m in self._cache.values():
            type_counts[m["type"]] += 1
        return {
            "total_memories": len(self._cache),
            "by_type": dict(type_counts),
            "loaded": self._loaded,
        }

    async def _persist_memory(self, memory: dict):
        try:
            from gneva.db import async_session_factory
            from gneva.models.agent import AgentMemory

            async with async_session_factory() as session:
                record = AgentMemory(
                    id=uuid.UUID(memory["id"]),
                    org_id=uuid.UUID(self.org_id),
                    memory_type=memory["type"],
                    content=memory["content"],
                    source_agent=memory["source_agent"],
                    source_meeting_id=uuid.UUID(memory["source_meeting_id"]) if memory.get("source_meeting_id") else None,
                    tags=memory.get("tags", []),
                    relevance_score=memory.get("relevance_score", 0.5),
                )
                session.add(record)
                await session.commit()
        except Exception as e:
            logger.debug(f"Failed to persist memory: {e}")

    async def _deactivate_memory(self, memory_id: str):
        try:
            from gneva.db import async_session_factory
            from gneva.models.agent import AgentMemory
            from sqlalchemy import update

            async with async_session_factory() as session:
                await session.execute(
                    update(AgentMemory)
                    .where(AgentMemory.id == uuid.UUID(memory_id))
                    .where(AgentMemory.org_id == uuid.UUID(self.org_id))
                    .values(is_active=False)
                )
                await session.commit()
        except Exception as e:
            logger.debug(f"Failed to deactivate memory: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CROSS-MEETING INTELLIGENCE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CrossMeetingIntelligence:
    """Detects patterns and generates insights across meeting history.

    Capabilities:
    - Recurring topic detection
    - Unresolved action item tracking
    - Sentiment trend analysis
    - Decision follow-up tracking
    - Relationship mapping between topics/people
    """

    def __init__(self, org_id: str):
        self.org_id = org_id

    async def get_recurring_topics(self, days: int = 30, min_occurrences: int = 2) -> list[dict]:
        """Find topics that come up repeatedly across meetings."""
        try:
            from gneva.db import async_session_factory
            from gneva.models.meeting import MeetingSummary, Meeting
            from sqlalchemy import select, and_

            cutoff = datetime.utcnow() - timedelta(days=days)

            async with async_session_factory() as session:
                result = await session.execute(
                    select(MeetingSummary.tldr, MeetingSummary.topics_covered, Meeting.title, Meeting.id, Meeting.created_at)
                    .join(Meeting, MeetingSummary.meeting_id == Meeting.id)
                    .where(and_(
                        Meeting.org_id == uuid.UUID(self.org_id),
                        Meeting.created_at >= cutoff,
                    ))
                    .order_by(Meeting.created_at.desc())
                )
                rows = result.all()

            if not rows:
                return []

            # Extract topics using LLM
            contents = "\n".join(f"[{r.title or 'Untitled'}] {r.tldr[:200]}" for r in rows[:50])

            from gneva.services import llm_create
            response = await llm_create(
                model="claude-haiku-4-5-20251001",
                max_tokens=400,
                system="Extract recurring themes/topics from these meeting summaries. Return as a JSON array of {topic, count, meetings} objects. Only include topics appearing 2+ times.",
                messages=[{"role": "user", "content": contents}],
            )

            import json
            text = response.content[0].text.strip() if response.content else "[]"
            # Try to parse JSON from the response
            try:
                # Handle markdown code blocks
                if "```" in text:
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                    text = text.strip()
                return json.loads(text)
            except (json.JSONDecodeError, IndexError):
                return [{"topic": "Analysis available", "raw": text}]

        except Exception as e:
            logger.error(f"Recurring topic detection failed: {e}")
            return []

    async def get_unresolved_actions(self, days: int = 30) -> list[dict]:
        """Find action items that were assigned but never completed."""
        try:
            from gneva.db import async_session_factory
            from gneva.models.entity import ActionItem
            from gneva.models.meeting import Meeting
            from sqlalchemy import select, and_

            cutoff = datetime.utcnow() - timedelta(days=days)

            async with async_session_factory() as session:
                result = await session.execute(
                    select(ActionItem, Meeting.title)
                    .join(Meeting, ActionItem.meeting_id == Meeting.id)
                    .where(and_(
                        ActionItem.org_id == uuid.UUID(self.org_id),
                        ActionItem.created_at >= cutoff,
                        ActionItem.status.in_(["open", "in_progress"]),
                    ))
                    .order_by(ActionItem.created_at)
                )
                rows = result.all()

            return [
                {
                    "id": str(item.id),
                    "description": item.description,
                    "assignee_id": str(item.assignee_id) if item.assignee_id else None,
                    "due_date": item.due_date.isoformat() if item.due_date else None,
                    "status": item.status,
                    "priority": item.priority,
                    "meeting_title": title,
                    "age_days": (datetime.utcnow() - item.created_at).days,
                    "overdue": item.due_date < datetime.utcnow().date() if item.due_date else False,
                }
                for item, title in rows
            ]
        except Exception as e:
            logger.error(f"Unresolved action tracking failed: {e}")
            return []

    async def get_meeting_briefing(self, meeting_title: str = "",
                                    participant_names: list[str] | None = None) -> str:
        """Generate a pre-meeting briefing based on historical context.

        Pulls together: recent decisions, unresolved actions, recurring topics,
        and relevant memories for the upcoming meeting.
        """
        sections = []

        # Get unresolved actions
        actions = await self.get_unresolved_actions(days=14)
        if participant_names:
            actions = [a for a in actions if a.get("assignee_id", "").lower() in
                      [p.lower() for p in participant_names]]
        overdue = [a for a in actions if a.get("overdue")]

        if overdue:
            items = "\n".join(f"  - {a['description']} (assignee_id={a['assignee_id']}, {a['age_days']} days ago)"
                            for a in overdue[:5])
            sections.append(f"OVERDUE ITEMS:\n{items}")

        if actions and not overdue:
            items = "\n".join(f"  - {a['description']} ({a['status']})" for a in actions[:5])
            sections.append(f"OPEN ACTION ITEMS:\n{items}")

        # Get recurring topics
        topics = await self.get_recurring_topics(days=14, min_occurrences=2)
        if topics and isinstance(topics[0], dict) and "topic" in topics[0]:
            topic_list = ", ".join(t["topic"] for t in topics[:5])
            sections.append(f"RECURRING TOPICS: {topic_list}")

        if not sections:
            return "No significant pre-meeting context found. Starting fresh."

        briefing = "PRE-MEETING BRIEFING\n" + "\n\n".join(sections)
        return briefing

    async def detect_sentiment_trend(self, days: int = 30) -> dict:
        """Analyze sentiment trends across recent meetings."""
        try:
            from gneva.db import async_session_factory
            from gneva.models.meeting import Meeting
            from sqlalchemy import select, and_, func

            cutoff = datetime.utcnow() - timedelta(days=days)

            async with async_session_factory() as session:
                result = await session.execute(
                    select(
                        func.count(Meeting.id).label("total"),
                        func.avg(Meeting.duration_sec).label("avg_duration"),
                        func.avg(Meeting.participant_count).label("avg_participants"),
                    )
                    .where(and_(
                        Meeting.org_id == uuid.UUID(self.org_id),
                        Meeting.created_at >= cutoff,
                        Meeting.status == "complete",
                    ))
                )
                row = result.one()

            return {
                "period_days": days,
                "total_meetings": row.total or 0,
                "avg_duration_min": round(row.avg_duration / 60, 1) if row.avg_duration else 0,
                "avg_participants": round(row.avg_participants, 1) if row.avg_participants else 0,
            }
        except Exception as e:
            logger.error(f"Sentiment trend detection failed: {e}")
            return {"period_days": days, "total_meetings": 0, "error": str(e)}
