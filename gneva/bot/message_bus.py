"""Inter-agent communication bus — structured messaging between agents in a meeting.

Message types:
- query: Request information from a specialist
- inform: Push information to an agent (no response expected)
- deliberate: Multi-agent parallel debate with synthesis
- delegate: Hand off question to another agent for public response
- correct: One agent corrects another's statement
- alert: Urgent notification (e.g. security issue, data anomaly)

Priority levels:
- low: Background, non-urgent (default)
- normal: Standard request
- high: Time-sensitive, should interrupt current processing
- critical: Emergency — security incident, system down, compliance breach
"""

import asyncio
import logging
import time
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Callable, Coroutine

from gneva.bot.defaults import (
    DEFAULT_AGENT_CONFIDENCE,
    DELIBERATION_CROSS_PCT,
    DELIBERATION_INITIAL_PCT,
    DELIBERATION_REVISE_PCT,
    MESSAGE_BUS_LOG_MAXLEN,
)

logger = logging.getLogger(__name__)

# Valid message types and their expected response behavior
MESSAGE_TYPES = {
    "query": {"expects_response": True, "max_response_time_sec": 15},
    "inform": {"expects_response": False, "max_response_time_sec": 0},
    "deliberate": {"expects_response": True, "max_response_time_sec": 30},
    "delegate": {"expects_response": True, "max_response_time_sec": 20},
    "correct": {"expects_response": False, "max_response_time_sec": 0},
    "alert": {"expects_response": False, "max_response_time_sec": 0},
}

PRIORITY_ORDER = {"low": 0, "normal": 1, "high": 2, "critical": 3}

# Visibility controls which messages are persisted and who can see them
VISIBILITY_LEVELS = {
    "internal": "Only agents see this",
    "meeting": "Visible in meeting record but not spoken",
    "public": "Will be spoken aloud to meeting participants",
}


class AgentMessage:
    """A single message in the inter-agent bus."""

    __slots__ = (
        "id", "meeting_id", "from_agent", "to_agent", "message_type",
        "content", "priority", "visibility", "metadata",
        "response_content", "response_confidence", "response_at",
        "created_at", "delivered_at", "ttl_sec",
    )

    def __init__(
        self,
        from_agent: str,
        to_agent: str,
        message_type: str,
        content: str,
        meeting_id: str | None = None,
        priority: str = "normal",
        visibility: str = "internal",
        metadata: dict | None = None,
        ttl_sec: float = 30,
    ):
        self.id = str(uuid.uuid4())
        self.meeting_id = meeting_id
        self.from_agent = from_agent
        self.to_agent = to_agent
        self.message_type = message_type
        self.content = content
        self.priority = priority
        self.visibility = visibility
        self.metadata = metadata or {}
        self.ttl_sec = ttl_sec

        self.response_content: str | None = None
        self.response_confidence: float | None = None
        self.response_at: float | None = None
        self.created_at: float = time.time()
        self.delivered_at: float | None = None

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_sec

    @property
    def priority_value(self) -> int:
        return PRIORITY_ORDER.get(self.priority, 1)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type,
            "content": self.content[:500],
            "priority": self.priority,
            "visibility": self.visibility,
            "response_content": self.response_content[:500] if self.response_content else None,
            "response_confidence": self.response_confidence,
            "created_at": self.created_at,
        }


class MessageBus:
    """Central message bus for inter-agent communication within a meeting.

    Features:
    - Priority-based message ordering
    - TTL-based message expiration
    - Handler registration per agent
    - Async delivery with timeout
    - Full message log for audit/analytics
    """

    def __init__(self, meeting_id: str):
        self.meeting_id = meeting_id

        # Handler registry: agent_name -> async handler(message) -> response_text
        self._handlers: dict[str, Callable[[AgentMessage], Coroutine[Any, Any, str | None]]] = {}

        # Message log (bounded)
        self._log: deque[AgentMessage] = deque(maxlen=MESSAGE_BUS_LOG_MAXLEN)

        # Pending responses: message_id -> asyncio.Future
        self._pending: dict[str, asyncio.Future] = {}

        # Stats
        self._stats = {
            "total_sent": 0,
            "total_delivered": 0,
            "total_expired": 0,
            "total_failed": 0,
            "by_type": {},
        }

    def register_handler(self, agent_name: str,
                         handler: Callable[[AgentMessage], Coroutine[Any, Any, str | None]]):
        """Register a message handler for an agent."""
        self._handlers[agent_name] = handler
        logger.debug(f"Message bus: registered handler for '{agent_name}'")

    def unregister_handler(self, agent_name: str):
        """Remove an agent's message handler."""
        self._handlers.pop(agent_name, None)

    async def send(self, message: AgentMessage) -> str | None:
        """Send a message and optionally wait for a response.

        Returns the response text if message_type expects a response, else None.
        """
        self._stats["total_sent"] += 1
        self._stats["by_type"][message.message_type] = (
            self._stats["by_type"].get(message.message_type, 0) + 1
        )
        self._log.append(message)

        if message.is_expired:
            self._stats["total_expired"] += 1
            logger.debug(f"Message {message.id} expired before delivery")
            return None

        handler = self._handlers.get(message.to_agent)
        if not handler:
            logger.debug(f"No handler for agent '{message.to_agent}', message dropped")
            self._stats["total_failed"] += 1
            return None

        msg_spec = MESSAGE_TYPES.get(message.message_type, {})
        expects_response = msg_spec.get("expects_response", False)
        timeout = msg_spec.get("max_response_time_sec", 15)

        try:
            response = await asyncio.wait_for(handler(message), timeout=timeout)
            message.delivered_at = time.time()
            self._stats["total_delivered"] += 1

            if response and expects_response:
                message.response_content = response
                message.response_at = time.time()

            # Fire-and-forget persistence (keep ref to suppress warnings)
            task = asyncio.create_task(self._persist(message))
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() and t.exception() else None)

            return response
        except asyncio.TimeoutError:
            logger.warning(f"Message to '{message.to_agent}' timed out ({timeout}s)")
            self._stats["total_failed"] += 1
            return None
        except Exception as e:
            logger.error(f"Message delivery to '{message.to_agent}' failed: {e}")
            self._stats["total_failed"] += 1
            return None

    async def broadcast(self, from_agent: str, agent_names: list[str],
                        message_type: str, content: str,
                        priority: str = "normal",
                        timeout: float = 15) -> dict[str, str | None]:
        """Send the same message to multiple agents in parallel.

        Returns: {agent_name: response_text_or_none}
        """
        if not agent_names:
            return {}

        tasks = {}
        for name in agent_names:
            msg = AgentMessage(
                from_agent=from_agent,
                to_agent=name,
                message_type=message_type,
                content=content,
                meeting_id=self.meeting_id,
                priority=priority,
                ttl_sec=timeout + 5,
            )
            tasks[name] = asyncio.create_task(self.send(msg))

        results = {}
        done, pending = await asyncio.wait(
            list(tasks.values()),
            timeout=timeout,
        )

        for name, task in tasks.items():
            if task in done:
                try:
                    results[name] = task.result()
                except Exception:
                    results[name] = None
            else:
                task.cancel()
                results[name] = None

        return results

    def get_log(self, last_n: int = 50, agent_filter: str | None = None) -> list[dict]:
        """Get recent message log entries."""
        entries = list(self._log)
        if agent_filter:
            entries = [
                m for m in entries
                if m.from_agent == agent_filter or m.to_agent == agent_filter
            ]
        return [m.to_dict() for m in entries[-last_n:]]

    def get_stats(self) -> dict:
        return dict(self._stats)

    async def _persist(self, message: AgentMessage):
        """Persist message to database (fire-and-forget)."""
        try:
            from gneva.db import async_session_factory
            from gneva.models.agent import AgentMessage as AgentMessageModel

            async with async_session_factory() as session:
                record = AgentMessageModel(
                    meeting_id=uuid.UUID(self.meeting_id),
                    from_agent=message.from_agent,
                    to_agent=message.to_agent,
                    message_type=message.message_type,
                    content=message.content[:2000],
                    urgency=message.priority,
                    visibility=message.visibility,
                    response_content=message.response_content[:2000] if message.response_content else None,
                    response_confidence=message.response_confidence,
                )
                session.add(record)
                await session.commit()
        except Exception as e:
            logger.debug(f"Failed to persist bus message: {e}")


class DeliberationProtocol:
    """Implements the 5-step deliberation protocol for multi-agent debate.

    Steps:
    1. Broadcast question (parallel) — all agents get the question simultaneously
    2. Collect initial positions (40% of time budget)
    3. Share positions for cross-pollination (30%) — each agent sees others' positions
    4. Collect revised positions (30%) — agents can update after seeing others
    5. Synthesize — Tia combines into unified response

    This is more thorough than the simple parallel-ask in AgentRouter.request_deliberation.
    Use for high-stakes decisions that benefit from cross-pollination.
    """

    def __init__(self, bus: MessageBus, synthesizer):
        """
        Args:
            bus: MessageBus instance for this meeting
            synthesizer: async callable(question, opinions) -> str
        """
        self.bus = bus
        self.synthesizer = synthesizer

    async def deliberate(
        self,
        question: str,
        agent_names: list[str],
        context: str = "",
        time_budget_sec: float = 30,
    ) -> dict:
        """Run full 5-step deliberation.

        Returns:
            {
                "synthesis": str,
                "initial_positions": {agent: str},
                "revised_positions": {agent: str},
                "consensus": bool,
                "dissenting": [agent_names],
                "time_taken": float,
            }
        """
        start = time.time()

        # Time allocation
        t_initial = time_budget_sec * DELIBERATION_INITIAL_PCT
        t_cross = time_budget_sec * DELIBERATION_CROSS_PCT
        t_revise = time_budget_sec * DELIBERATION_REVISE_PCT

        full_prompt = f"{question}\n\nContext: {context}" if context else question

        # Step 1+2: Broadcast question, collect initial positions
        initial = await self.bus.broadcast(
            from_agent="tia",
            agent_names=agent_names,
            message_type="deliberate",
            content=f"INITIAL POSITION REQUEST:\n{full_prompt}\n\nProvide your initial position in 2-3 sentences. Include your confidence level (low/medium/high).",
            timeout=t_initial,
        )
        initial_positions = {k: v for k, v in initial.items() if v}

        if not initial_positions:
            return {
                "synthesis": "I couldn't get input from any specialists on this.",
                "initial_positions": {},
                "revised_positions": {},
                "consensus": False,
                "dissenting": [],
                "time_taken": round(time.time() - start, 1),
            }

        # Step 3+4: Cross-pollination — share positions, collect revisions
        positions_summary = "\n\n".join(
            f"{name}: {pos}" for name, pos in initial_positions.items()
        )

        revised = await self.bus.broadcast(
            from_agent="tia",
            agent_names=list(initial_positions.keys()),
            message_type="deliberate",
            content=(
                f"CROSS-POLLINATION — revise or confirm your position.\n\n"
                f"Original question: {question}\n\n"
                f"Other agents' positions:\n{positions_summary}\n\n"
                f"After seeing other perspectives, provide your final position in 2-3 sentences. "
                f"Note if you changed your mind and why. Include confidence (low/medium/high)."
            ),
            timeout=t_cross + t_revise,
        )
        revised_positions = {k: v or initial_positions.get(k, "") for k, v in revised.items()}

        # Step 5: Detect consensus/dissent and synthesize
        opinions = [
            {
                "agent": name,
                "display_name": name.capitalize(),
                "initial": initial_positions.get(name, ""),
                "revised": revised_positions.get(name, ""),
                "position": revised_positions.get(name, initial_positions.get(name, "")),
                "confidence": DEFAULT_AGENT_CONFIDENCE,
            }
            for name in agent_names
            if name in initial_positions
        ]

        synthesis = await self.synthesizer(question, opinions)

        # Consensus detection: check for dissent signals in revised positions
        dissenting = []
        _dissent_phrases = [
            "i disagree", "push back", "changed my mind", "i don't think",
            "i'm not convinced", "my concern is", "i'd argue against",
            "that's wrong", "i differ", "opposing view",
        ]
        _agreement_phrases = [
            "i agree", "no need to push back", "on the same page",
            "makes sense", "aligned", "consensus",
        ]
        for name in initial_positions:
            revised_text = revised_positions.get(name, "").lower()
            has_dissent = any(p in revised_text for p in _dissent_phrases)
            has_agreement = any(p in revised_text for p in _agreement_phrases)
            # Only flag as dissenting if dissent phrases found WITHOUT agreement override
            if has_dissent and not has_agreement:
                dissenting.append(name)

        return {
            "synthesis": synthesis,
            "initial_positions": initial_positions,
            "revised_positions": revised_positions,
            "consensus": len(dissenting) == 0,
            "dissenting": dissenting,
            "time_taken": round(time.time() - start, 1),
        }
