"""Real-time meeting context engine — live transcript processing, interjection logic."""

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.config import get_settings
from gneva.db import async_session_factory
from gneva.models.entity import Decision, Entity

logger = logging.getLogger(__name__)
settings = get_settings()

# Patterns that signal a question directed at Gneva
GNEVA_TRIGGERS = re.compile(
    r"\b(?:gneva|geneva)\b.*\?|"
    r"\bhey\s+(?:gneva|geneva)\b|"
    r"\b(?:gneva|geneva),?\s+(?:what|when|who|how|why|can you|do you|did we)",
    re.IGNORECASE,
)

QUESTION_PATTERNS = re.compile(
    r"(?:does anyone (?:remember|know|recall)|"
    r"what (?:did we|was the) (?:decide|agree|say)|"
    r"when did we (?:last|decide)|"
    r"didn't we already|"
    r"have we discussed)",
    re.IGNORECASE,
)


@dataclass
class LiveSegment:
    speaker: str
    text: str
    timestamp: float


@dataclass
class MeetingState:
    meeting_id: uuid.UUID
    org_id: uuid.UUID | None = None
    segments: list[LiveSegment] = field(default_factory=list)
    speakers: set[str] = field(default_factory=set)
    topics: list[str] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)
    last_gneva_spoke: float = 0.0
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    @property
    def full_text(self) -> str:
        return " ".join(s.text for s in self.segments[-50:])


class RealtimeEngine:
    """Processes live transcript segments and decides when Gneva should contribute."""

    # Minimum seconds between Gneva interjections
    COOLDOWN_SEC = 30.0
    # Maximum age of inactive meeting state before cleanup (5 hours)
    MEETING_TTL_SEC = 5 * 3600

    def __init__(self):
        self._meetings: dict[uuid.UUID, MeetingState] = {}

    def _get_state(self, meeting_id: uuid.UUID) -> MeetingState:
        # TTL cleanup: remove meetings with no activity for MEETING_TTL_SEC
        now = time.time()
        stale_ids = [
            mid for mid, state in self._meetings.items()
            if now - state.last_activity > self.MEETING_TTL_SEC
        ]
        for mid in stale_ids:
            logger.info("Cleaning up stale meeting state: %s", mid)
            del self._meetings[mid]

        if meeting_id not in self._meetings:
            self._meetings[meeting_id] = MeetingState(meeting_id=meeting_id)
        return self._meetings[meeting_id]

    # ------------------------------------------------------------------
    # Process incoming live segment
    # ------------------------------------------------------------------
    async def process_live_segment(
        self, meeting_id: uuid.UUID, text: str, speaker: str, org_id: uuid.UUID | None = None,
    ) -> None:
        """Ingest a real-time transcript segment and update meeting state."""
        state = self._get_state(meeting_id)
        if org_id:
            state.org_id = org_id
        now = time.time()
        state.segments.append(LiveSegment(speaker=speaker, text=text, timestamp=now))
        state.speakers.add(speaker)
        state.last_activity = now

        # Keep segments bounded
        if len(state.segments) > 200:
            state.segments = state.segments[-150:]

    # ------------------------------------------------------------------
    # Should Gneva speak?
    # ------------------------------------------------------------------
    async def should_gneva_speak(self, meeting_id: uuid.UUID) -> tuple[bool, str | None]:
        """Decide whether Gneva should interject, and with what response.

        Returns (should_speak, response_text).
        """
        state = self._get_state(meeting_id)
        if not state.segments:
            return False, None

        now = time.time()
        if now - state.last_gneva_spoke < self.COOLDOWN_SEC:
            return False, None

        latest = state.segments[-1]

        # 1. Direct address
        if self._check_for_question(latest.text):
            response = await self._generate_response(
                meeting_id, trigger="direct_question", context=latest.text,
            )
            if response:
                state.last_gneva_spoke = now
                return True, response

        # 2. General question that Gneva can answer from memory
        if state.org_id and QUESTION_PATTERNS.search(latest.text):
            response = await self._generate_response(
                meeting_id, trigger="memory_question", context=latest.text,
            )
            if response:
                state.last_gneva_spoke = now
                return True, response

        # 3. Contradiction with past decisions
        if state.org_id and len(state.segments) >= 3:
            contradiction = await self._check_for_contradiction(state.org_id, latest.text)
            if contradiction:
                state.last_gneva_spoke = now
                return True, contradiction

        # 4. Context opportunity (every 20 segments, check if past context would help)
        if len(state.segments) % 20 == 0 and state.org_id:
            context_note = await self._check_for_context_opportunity(meeting_id)
            if context_note:
                state.last_gneva_spoke = now
                return True, context_note

        return False, None

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------
    def _check_for_question(self, text: str) -> bool:
        """Detect if the text contains a question directed at Gneva."""
        return bool(GNEVA_TRIGGERS.search(text))

    async def _check_for_contradiction(self, org_id: uuid.UUID, text: str) -> str | None:
        """Check if statement contradicts a previous decision."""
        async with async_session_factory() as db:
            decisions = (await db.execute(
                select(Decision)
                .where(Decision.org_id == org_id, Decision.status == "active")
                .order_by(Decision.created_at.desc())
                .limit(20)
            )).scalars().all()

        if not decisions:
            return None

        decision_context = "\n".join(f"- {d.statement}" for d in decisions)
        text_lower = text.lower()

        # Quick keyword overlap check before calling LLM
        has_overlap = any(
            word in text_lower
            for d in decisions
            for word in d.statement.lower().split()
            if len(word) > 4
        )
        if not has_overlap:
            return None

        if not settings.anthropic_api_key:
            return None

        from gneva.services import get_anthropic_client
        client = get_anthropic_client()

        def _call():
            return client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                system=(
                    "You are Gneva, an AI meeting participant. Given previous decisions and a new statement, "
                    "determine if there's a contradiction. If yes, respond with a brief, polite note like: "
                    "'Just a heads up — this seems to differ from the decision on [date] to [decision]. "
                    "Should we revisit that?' If no contradiction, respond with exactly: NO_CONTRADICTION"
                ),
                messages=[{"role": "user", "content": f"Previous decisions:\n{decision_context}\n\nNew statement: {text}"}],
            )

        resp = await asyncio.to_thread(_call)
        answer = resp.content[0].text.strip()
        if answer == "NO_CONTRADICTION":
            return None
        return answer

    async def _check_for_context_opportunity(self, meeting_id: uuid.UUID) -> str | None:
        """Check if past context could enrich the current discussion."""
        state = self._get_state(meeting_id)
        if not state.org_id:
            return None

        recent_text = " ".join(s.text for s in state.segments[-10:])

        # Extract potential entity names (capitalize words > 3 chars)
        words = set(w for w in recent_text.split() if len(w) > 3 and w[0].isupper())
        if not words:
            return None

        async with async_session_factory() as db:
            from sqlalchemy import or_
            conditions = [Entity.name.ilike(f"%{w}%") for w in list(words)[:5]]
            entities = (await db.execute(
                select(Entity)
                .where(Entity.org_id == state.org_id)
                .where(or_(*conditions))
                .where(Entity.mention_count >= 3)
                .order_by(Entity.mention_count.desc())
                .limit(3)
            )).scalars().all()

        if not entities:
            return None

        # Only interject if there's substantive context to add
        notable = [e for e in entities if e.description and len(e.description) > 20]
        if not notable:
            return None

        notes = "; ".join(f"{e.name}: {e.description[:100]}" for e in notable[:2])
        return f"For context — {notes}"

    # ------------------------------------------------------------------
    # Response generation
    # ------------------------------------------------------------------
    async def _generate_response(
        self, meeting_id: uuid.UUID, trigger: str, context: str,
    ) -> str | None:
        """Generate Gneva's spoken response using Claude Haiku for speed."""
        state = self._get_state(meeting_id)

        # Gather org memory context
        memory_context = ""
        if state.org_id:
            async with async_session_factory() as db:
                entities = (await db.execute(
                    select(Entity)
                    .where(Entity.org_id == state.org_id)
                    .where(Entity.name.ilike(f"%{context.split()[-1] if context.split() else ''}%"))
                    .order_by(Entity.mention_count.desc())
                    .limit(5)
                )).scalars().all()
                if entities:
                    memory_context = "\n".join(
                        f"[{e.type}] {e.name}: {e.description or 'N/A'}" for e in entities
                    )

        recent_transcript = "\n".join(
            f"{s.speaker}: {s.text}" for s in state.segments[-10:]
        )

        if not settings.anthropic_api_key:
            logger.warning("No Anthropic key — cannot generate realtime response")
            return None

        from gneva.services import get_anthropic_client
        client = get_anthropic_client()

        system_prompt = (
            "You are Gneva, an AI team member participating in a live meeting. "
            "Keep responses brief (1-2 sentences), conversational, and helpful. "
            "If you don't have relevant information, say so briefly. "
            "Never be preachy or over-explain. Sound natural."
        )

        user_msg = f"Trigger: {trigger}\n\nRecent transcript:\n{recent_transcript}"
        if memory_context:
            user_msg += f"\n\nRelevant org memory:\n{memory_context}"
        user_msg += f"\n\nRespond to: {context}"

        try:
            def _call():
                return client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=150,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_msg}],
                )

            resp = await asyncio.to_thread(_call)
            return resp.content[0].text.strip()
        except Exception:
            logger.exception("Failed to generate realtime response")
            return None

    # ------------------------------------------------------------------
    # Live context API
    # ------------------------------------------------------------------
    def get_live_context(self, meeting_id: uuid.UUID) -> dict:
        """Return current meeting context for API consumers."""
        state = self._meetings.get(meeting_id)
        if not state:
            return {"meeting_id": str(meeting_id), "active": False}

        return {
            "meeting_id": str(meeting_id),
            "active": True,
            "duration_sec": int(time.time() - state.created_at),
            "speakers": sorted(state.speakers),
            "segment_count": len(state.segments),
            "topics": state.topics,
            "key_points": state.key_points,
            "recent_segments": [
                {"speaker": s.speaker, "text": s.text, "ts": s.timestamp}
                for s in state.segments[-10:]
            ],
        }

    def end_meeting(self, meeting_id: uuid.UUID) -> None:
        """Clean up state for a finished meeting."""
        self._meetings.pop(meeting_id, None)
