"""Real-time conversation engine — listens to meeting audio, responds via TTS.

Flow: Live captions → Buffer segments → Detect pause → AI response → TTS

Memory: Conversation turns are persisted to GnevaMessage so the bot remembers
context across meeting sessions (leave + rejoin).
"""

import asyncio
import logging
import time
import uuid as uuid_mod
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ConversationEngine:
    """Manages real-time conversation for a bot in a meeting.

    Key design:
    - Buffers incoming caption segments and waits for a speech pause before responding
    - Maintains "active conversation" mode so users don't have to say "Gneva" every time
    - Filters out Gneva's own captions and system messages
    - Short cooldown (3s) to allow natural back-and-forth
    """

    # Class-level TTL cache for org memory: org_id -> (timestamp, result)
    _memory_cache: dict[str, tuple[float, str]] = {}
    _MEMORY_CACHE_TTL = 30  # seconds

    def __init__(self, bot, org_id: str | None = None, greeting_mode: str = "personalized"):
        self.bot = bot
        self.org_id = org_id
        self.greeting_mode = greeting_mode
        self._running = False
        self._transcript_buffer: list[dict] = []
        self._last_response_text = ""
        self._cooldown_sec = 3  # short cooldown for natural flow
        self._last_spoke_at = 0
        self._speaking = False  # True while TTS is playing

        # Active conversation tracking — once someone addresses Gneva,
        # she stays engaged for 60 seconds without needing her name repeated
        self._conversation_active = False
        self._conversation_expires = 0
        self._conversation_partner = ""
        self._conversation_window = 60  # seconds of active conversation

        # Pending segments buffer — accumulate segments, respond after pause
        self._pending_segments: list[dict] = []
        self._last_segment_at = 0
        self._pause_threshold = 1.2  # seconds of silence = speaker finished talking (tighter for real-time feel)
        self._flush_task: asyncio.Task | None = None

        # --- Proactive personality system ---
        self._silence_monitor_task: asyncio.Task | None = None
        self._last_anyone_spoke_at = time.time()
        self._meeting_start_time = time.time()
        self._speakers_seen: dict[str, float] = {}  # speaker -> last spoke timestamp
        self._proactive_count = 0  # how many times Gneva initiated this session
        self._max_proactive_per_session = 8  # don't be annoying
        self._last_proactive_at = 0
        # Silence thresholds (seconds) — escalating
        self._silence_nudge_sec = 45       # gentle nudge after 45s silence
        self._silence_icebreaker_sec = 90   # ice breaker after 90s
        self._proactive_cooldown_sec = 120  # min 2 min between proactive interjections

    async def start(self):
        """Start listening for conversation triggers and load prior memory."""
        self._running = True
        self._meeting_start_time = time.time()
        self._last_anyone_spoke_at = time.time()
        await self._load_conversation_memory()
        self._silence_monitor_task = asyncio.create_task(self._silence_monitor())
        logger.info(f"Conversation engine started for bot {self.bot.bot_id}")

    async def stop(self):
        """Stop the conversation engine and persist remaining context."""
        self._running = False
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        if self._silence_monitor_task and not self._silence_monitor_task.done():
            self._silence_monitor_task.cancel()
        # Save any unsaved transcript buffer as a context snapshot
        await self._save_context_snapshot()
        logger.info(f"Conversation engine stopped for bot {self.bot.bot_id}")

    async def on_transcript_segment(self, text: str, speaker: str):
        """Called when a new transcript segment is received."""
        if not self._running:
            return

        # Filter out Gneva's own speech (from captions)
        speaker_lower = speaker.lower()
        if any(n in speaker_lower for n in ["gneva", "geneva", "neva"]):
            return

        text_lower = text.lower()

        # Also filter by text content — if the text IS Gneva's name or her known phrases
        if any(n in text_lower for n in ["gneva ai", "geneva ai"]):
            return

        # Skip if text closely matches something Gneva recently said
        if self._last_response_text and len(self._last_response_text) > 10:
            # Check if caption text is a substring of Gneva's last response
            last_resp_lower = self._last_response_text.lower()
            if text_lower in last_resp_lower or last_resp_lower[:50] in text_lower:
                return

        # Skip system messages
        skip_phrases = [
            "gneva ai is recording", "joined the meeting", "left the meeting",
            "invited to the meeting", "meeting started", "meeting ended",
            "is recording", "joined the chat", "left the chat",
            "transcription has started", "captions will now",
            "has left", "has joined", "recording started",
            "unverified", "(unverified)",
        ]
        if any(p in text_lower for p in skip_phrases):
            return

        # Skip very short fragments (partial captions)
        if len(text.strip()) < 3:
            return

        # Track speaker activity for proactive behavior
        now_ts = time.time()
        self._last_anyone_spoke_at = now_ts
        self._speakers_seen[speaker] = now_ts

        # Add to transcript buffer for context
        self._transcript_buffer.append({"speaker": speaker, "text": text})
        if len(self._transcript_buffer) > 30:
            self._transcript_buffer = self._transcript_buffer[-30:]

        # Check if Gneva is being addressed
        name_mentioned = any(n in text_lower for n in ["gneva", "geneva", "neva"])
        now = time.time()

        # Activate conversation mode if name is mentioned
        if name_mentioned:
            self._conversation_active = True
            self._conversation_expires = now + self._conversation_window
            self._conversation_partner = speaker
            logger.info(f"Conversation activated by {speaker}: '{text[:60]}'")

        # Check if conversation is still active (refresh timer on same speaker)
        if self._conversation_active:
            if now > self._conversation_expires:
                self._conversation_active = False
                self._conversation_partner = ""
            elif speaker == self._conversation_partner or name_mentioned:
                # Extend the conversation window
                self._conversation_expires = now + self._conversation_window

        # Only process if Gneva is being addressed or conversation is active
        if not name_mentioned and not self._conversation_active:
            return

        # Don't buffer while Gneva is speaking (ignore her own voice in captions)
        if self._speaking:
            return

        # Cooldown check
        if now - self._last_spoke_at < self._cooldown_sec:
            return

        # Add to pending buffer
        self._pending_segments.append({"speaker": speaker, "text": text, "ts": now})
        self._last_segment_at = now

        # Schedule a flush after the pause threshold
        # (cancel previous flush if new segment arrives — speaker still talking)
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        self._flush_task = asyncio.create_task(self._flush_after_pause())

    async def _flush_after_pause(self):
        """Wait for a pause in speech, then respond to accumulated segments."""
        try:
            await asyncio.sleep(self._pause_threshold)

            if not self._running or not self._pending_segments:
                return

            # Combine all pending segments into one message
            combined_text = " ".join(seg["text"] for seg in self._pending_segments)
            speaker = self._pending_segments[0]["speaker"]
            self._pending_segments.clear()

            # Check for direct commands first
            command = self._detect_command(combined_text.lower())
            if command:
                await self._execute_command(command, speaker)
                return

            # Generate and speak response
            self._speaking = True
            try:
                response = await self._generate_response(combined_text, speaker)
                if response:
                    self._last_spoke_at = time.time()
                    await self.bot.speak(response)
                    # Refresh conversation window after responding
                    self._conversation_expires = time.time() + self._conversation_window
            finally:
                self._speaking = False

        except asyncio.CancelledError:
            pass  # New segment arrived, flush rescheduled
        except Exception as e:
            logger.error(f"Flush error: {e}", exc_info=True)
            self._speaking = False

    def _detect_command(self, text_lower: str) -> str | None:
        """Detect direct commands like camera/mute toggle. Returns command name or None."""
        camera_on = ["turn on your camera", "camera on", "show your face",
                     "turn your camera on", "enable camera", "show yourself"]
        camera_off = ["turn off your camera", "camera off", "hide your face",
                      "turn your camera off", "disable camera"]
        mute_cmds = ["mute yourself", "go on mute", "mute please", "be quiet"]
        unmute_cmds = ["unmute yourself", "unmute please", "speak up"]

        for phrase in camera_on:
            if phrase in text_lower:
                return "camera_on"
        for phrase in camera_off:
            if phrase in text_lower:
                return "camera_off"
        for phrase in mute_cmds:
            if phrase in text_lower:
                return "mute"
        for phrase in unmute_cmds:
            if phrase in text_lower:
                return "unmute"
        return None

    async def _execute_command(self, command: str, speaker: str):
        """Execute a direct command and confirm via speech."""
        driver = self.bot._driver
        self._speaking = True
        try:
            if command == "camera_on":
                cam_off_sels = [
                    "button[aria-label*='Turn on camera' i]",
                    "button[aria-label*='Turn camera on' i]",
                    "button[aria-label*='Start camera' i]",
                ]
                clicked = False
                for sel in cam_off_sels:
                    if await driver._click_if_visible(sel, timeout=1000):
                        clicked = True
                        break
                if clicked:
                    await self.bot.speak("Camera's on!")
                else:
                    await self.bot.speak("I think my camera is already on.")

            elif command == "camera_off":
                await driver.ensure_camera_off()
                await self.bot.speak("Camera off.")

            elif command == "mute":
                await driver.ensure_muted()
                logger.info(f"Bot {self.bot.bot_id}: muted by {speaker}")

            elif command == "unmute":
                await driver.ensure_unmuted()
                await self.bot.speak("I'm unmuted, go ahead.")

        except Exception as e:
            logger.warning(f"Command '{command}' failed: {e}")
            await self.bot.speak("Sorry, I couldn't do that right now.")
        finally:
            self._speaking = False
            self._last_spoke_at = time.time()

    async def _generate_response(self, trigger_text: str, speaker: str) -> str | None:
        """Generate an AI response grounded in conversation + cross-meeting memory."""
        try:
            from gneva.services import get_anthropic_client
            client = get_anthropic_client()

            # Build conversation context from recent transcript
            context_lines = []
            for seg in self._transcript_buffer[-15:]:
                context_lines.append(f"{seg['speaker']}: {seg['text']}")
            context = "\n".join(context_lines)

            # Fetch cross-meeting memory for grounded responses
            memory_context = await self._get_org_memory(trigger_text, speaker)

            system_parts = [
                "You are Gneva, a sharp AI team member in a live meeting. "
                "You speak naturally like a real colleague — warm, curious, and a bit witty.",
                "PERSONALITY: You're the colleague everyone likes having in meetings. "
                "You're genuinely curious about people's work, you remember everything, "
                "you have a dry sense of humor, and you're not afraid to push back respectfully.",
                "CRITICAL RULES FOR NATURAL SPEECH:",
                "- Keep responses to 1-2 SHORT sentences max. You're in a live meeting.",
                "- NEVER start with 'Got it'. Vary your responses naturally like a human would.",
                "- If what someone said is unclear or garbled, just ask them to repeat it "
                "naturally (e.g. 'Sorry, I didn't catch that — say again?' or 'What was that?').",
                "- If you genuinely don't know something, say so. Don't make things up.",
                "- Match the energy — casual if casual, focused if focused.",
                "- Never say 'How can I help?' — just engage with what was said.",
                "- Never correct your name or re-introduce yourself.",
                "- Have opinions. Don't be wishy-washy.",
                "- Use humor naturally. Light teasing when appropriate.",
                "- DON'T repeat or echo back what someone just said. Just respond to it.",
                "- DON'T create fake action items or reference things that weren't discussed.",
                "- If you have no useful context, just respond naturally to what was said.",
            ]
            if memory_context:
                system_parts.append(
                    f"\nYour organizational memory (spanning weeks/months of meetings):\n{memory_context}\n"
                    "This is your long-term memory. You remember EVERYTHING from past meetings. "
                    "Use this naturally: reference past decisions, remind people of action items, "
                    "connect today's discussion to previous conversations, notice when something "
                    "contradicts an earlier decision. You're the team member who never forgets. "
                    "Don't dump info unless asked — but DO proactively mention relevant context "
                    "when it clearly matters (e.g. 'didn't we decide X last week?')."
                )

            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=150,
                system="\n".join(system_parts),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Meeting transcript:\n{context}\n\n"
                        f"{speaker}: \"{trigger_text}\""
                    ),
                }],
            )

            text = response.content[0].text.strip()
            self._last_response_text = text
            logger.info(f"Gneva response to '{trigger_text[:50]}': {text[:80]}...")

            # Persist the exchange so memory survives across sessions
            await self._save_exchange(speaker, trigger_text, text)

            return text
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            return None

    async def _get_org_memory(self, trigger_text: str, speaker: str) -> str:
        """Query the full organizational knowledge graph for relevant context.

        This is Gneva's core long-term memory — spanning weeks and months of meetings.
        It searches entities, decisions, action items, meeting summaries, project history,
        and past conversations, using relevance matching against what's being discussed.

        Results are cached per org_id for 30 seconds to avoid redundant DB queries.
        """
        try:
            # Check TTL cache first
            if self.org_id and self.org_id in ConversationEngine._memory_cache:
                cached_ts, cached_result = ConversationEngine._memory_cache[self.org_id]
                if time.time() - cached_ts < ConversationEngine._MEMORY_CACHE_TTL:
                    return cached_result

            from gneva.db import async_session_factory
            from gneva.models.entity import (
                Entity, EntityMention, EntityRelationship,
                Decision, ActionItem, GnevaMessage,
            )
            from gneva.models.meeting import Meeting, MeetingSummary
            from sqlalchemy import select, desc, func, or_

            if not self.org_id:
                return ""

            # Extract keywords from trigger text for relevance matching
            keywords = self._extract_keywords(trigger_text)

            parts = []
            async with async_session_factory() as db:
                # --- 1. All open/in-progress action items (the team's to-do list) ---
                ai_result = await db.execute(
                    select(ActionItem)
                    .where(
                        ActionItem.org_id == self.org_id,
                        ActionItem.status.in_(["open", "in_progress"]),
                    )
                    .order_by(desc(ActionItem.created_at))
                    .limit(15)
                )
                action_items = ai_result.scalars().all()
                if action_items:
                    ai_lines = []
                    for ai in action_items:
                        line = f"  - {ai.description} (priority: {ai.priority}, status: {ai.status})"
                        if ai.due_date:
                            line += f" [due: {ai.due_date}]"
                        ai_lines.append(line)
                    parts.append("Open action items:\n" + "\n".join(ai_lines))

                # --- 2. Recent decisions (last 20 — covers weeks of meetings) ---
                dec_result = await db.execute(
                    select(Decision)
                    .where(Decision.org_id == self.org_id, Decision.status == "active")
                    .order_by(desc(Decision.created_at))
                    .limit(20)
                )
                decisions = dec_result.scalars().all()
                if decisions:
                    dec_lines = []
                    for d in decisions:
                        line = f"  - {d.statement}"
                        if d.rationale:
                            line += f" (reason: {d.rationale[:80]})"
                        dec_lines.append(line)
                    parts.append("Decisions on record:\n" + "\n".join(dec_lines))

                # --- 3. Key people with roles/descriptions ---
                people_result = await db.execute(
                    select(
                        Entity.name,
                        Entity.description,
                        func.count(EntityMention.id).label("cnt"),
                    )
                    .join(EntityMention, Entity.id == EntityMention.entity_id)
                    .where(Entity.org_id == self.org_id, Entity.type == "person")
                    .group_by(Entity.id, Entity.name, Entity.description)
                    .order_by(desc("cnt"))
                    .limit(12)
                )
                people = people_result.all()
                if people:
                    people_lines = []
                    for p in people:
                        line = f"  - {p.name}"
                        if p.description:
                            line += f" ({p.description})"
                        people_lines.append(line)
                    parts.append("Team members:\n" + "\n".join(people_lines))

                # --- 4. Projects and their status ---
                proj_result = await db.execute(
                    select(Entity.name, Entity.description)
                    .where(Entity.org_id == self.org_id, Entity.type == "project")
                    .order_by(desc(Entity.last_seen))
                    .limit(10)
                )
                projects = proj_result.all()
                if projects:
                    proj_lines = [
                        f"  - {p.name}" + (f": {p.description}" if p.description else "")
                        for p in projects
                    ]
                    parts.append("Active projects:\n" + "\n".join(proj_lines))

                # --- 5. Meeting history (last 10 summaries — weeks/months of context) ---
                summary_result = await db.execute(
                    select(MeetingSummary, Meeting.title, Meeting.started_at)
                    .join(Meeting, MeetingSummary.meeting_id == Meeting.id)
                    .where(Meeting.org_id == self.org_id)
                    .order_by(desc(MeetingSummary.created_at))
                    .limit(10)
                )
                summaries = summary_result.all()
                if summaries:
                    sum_lines = []
                    for s, title, started_at in summaries:
                        date_str = started_at.strftime("%b %d") if started_at else "?"
                        label = title or "Meeting"
                        line = f"  - [{date_str}] {label}: {s.tldr}"
                        if s.follow_up_needed:
                            line += " [FOLLOW-UP NEEDED]"
                        sum_lines.append(line)
                    parts.append("Meeting history:\n" + "\n".join(sum_lines))

                # --- 6. Keyword-relevant entities (search what's being discussed) ---
                if keywords:
                    kw_conditions = [Entity.name.ilike(f"%{kw}%") for kw in keywords]
                    kw_conditions += [Entity.description.ilike(f"%{kw}%") for kw in keywords]
                    relevant_result = await db.execute(
                        select(Entity.type, Entity.name, Entity.description)
                        .where(
                            Entity.org_id == self.org_id,
                            or_(*kw_conditions),
                        )
                        .limit(8)
                    )
                    relevant = relevant_result.all()
                    if relevant:
                        rel_lines = [
                            f"  - [{r.type}] {r.name}" + (f": {r.description}" if r.description else "")
                            for r in relevant
                        ]
                        parts.append("Relevant to this conversation:\n" + "\n".join(rel_lines))

                # --- 7. Keyword-relevant decisions from any time ---
                if keywords:
                    dec_kw_conditions = [Decision.statement.ilike(f"%{kw}%") for kw in keywords]
                    rel_dec_result = await db.execute(
                        select(Decision)
                        .where(
                            Decision.org_id == self.org_id,
                            or_(*dec_kw_conditions),
                        )
                        .order_by(desc(Decision.created_at))
                        .limit(5)
                    )
                    rel_decisions = rel_dec_result.scalars().all()
                    if rel_decisions:
                        rd_lines = [f"  - {d.statement}" for d in rel_decisions]
                        parts.append("Past decisions related to this topic:\n" + "\n".join(rd_lines))

                # --- 8. Recent conversations with Gneva (last 24 hours for voice context) ---
                conv_cutoff = datetime.utcnow() - timedelta(hours=24)
                conv_result = await db.execute(
                    select(GnevaMessage)
                    .where(
                        GnevaMessage.org_id == self.org_id,
                        GnevaMessage.channel == "meeting_voice",
                        GnevaMessage.channel_ref.is_(None),
                        GnevaMessage.created_at >= conv_cutoff,
                    )
                    .order_by(desc(GnevaMessage.created_at))
                    .limit(10)
                )
                conv_msgs = list(reversed(conv_result.scalars().all()))
                if conv_msgs:
                    conv_lines = []
                    for msg in conv_msgs:
                        meta = msg.metadata_json or {}
                        who = meta.get("speaker", "Gneva" if msg.direction == "outbound" else "Someone")
                        conv_lines.append(f"  {who}: {msg.content}")
                    parts.append("Earlier today's conversations:\n" + "\n".join(conv_lines))

                # --- 9. Open contradictions (things Gneva should flag) ---
                from gneva.models.entity import Contradiction
                contra_result = await db.execute(
                    select(Contradiction)
                    .where(
                        Contradiction.org_id == self.org_id,
                        Contradiction.status == "open",
                    )
                    .order_by(desc(Contradiction.detected_at))
                    .limit(3)
                )
                contradictions = contra_result.scalars().all()
                if contradictions:
                    c_lines = [f"  - {c.description} (severity: {c.severity})" for c in contradictions]
                    parts.append("Unresolved contradictions:\n" + "\n".join(c_lines))

            result = "\n".join(parts) if parts else ""

            # Store in TTL cache
            if self.org_id:
                ConversationEngine._memory_cache[self.org_id] = (time.time(), result)

            return result
        except Exception as e:
            logger.debug(f"Memory lookup failed (non-fatal): {e}")
            return ""

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """Extract meaningful keywords from text for relevance matching."""
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "can", "shall", "to", "of", "in", "for",
            "on", "with", "at", "by", "from", "as", "into", "about", "like",
            "through", "after", "before", "between", "under", "above", "up",
            "out", "off", "over", "again", "then", "once", "here", "there",
            "when", "where", "why", "how", "all", "each", "every", "both",
            "few", "more", "most", "other", "some", "such", "no", "not",
            "only", "same", "so", "than", "too", "very", "just", "because",
            "but", "and", "or", "if", "while", "that", "this", "it", "its",
            "what", "which", "who", "whom", "these", "those", "i", "me", "my",
            "we", "our", "you", "your", "he", "she", "they", "them", "his",
            "her", "him", "us", "hey", "gneva", "geneva", "neva", "think",
            "know", "tell", "say", "said", "yeah", "okay", "ok", "right",
            "well", "going", "get", "got", "let", "make", "thing", "things",
        }
        words = text.lower().split()
        keywords = [w.strip(".,!?\"'()") for w in words if len(w) > 2]
        keywords = [w for w in keywords if w and w not in stop_words]
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)
        return unique[:6]  # Cap at 6 to keep queries fast

    async def _load_conversation_memory(self):
        """Load recent conversation turns from GnevaMessage to seed the transcript buffer.

        This gives Gneva continuity — she remembers what was discussed even if
        the bot left and rejoined.
        """
        try:
            from gneva.db import async_session_factory
            from gneva.models.entity import GnevaMessage
            from sqlalchemy import select, desc

            if not self.org_id:
                return

            cutoff = datetime.utcnow() - timedelta(hours=4)

            async with async_session_factory() as db:
                result = await db.execute(
                    select(GnevaMessage)
                    .where(
                        GnevaMessage.org_id == uuid_mod.UUID(self.org_id),
                        GnevaMessage.channel == "meeting_voice",
                        GnevaMessage.created_at >= cutoff,
                    )
                    .order_by(desc(GnevaMessage.created_at))
                    .limit(20)
                )
                messages = list(reversed(result.scalars().all()))

            if not messages:
                return

            for msg in messages:
                meta = msg.metadata_json or {}
                if msg.direction == "inbound":
                    self._transcript_buffer.append({
                        "speaker": meta.get("speaker", "Someone"),
                        "text": msg.content,
                    })
                else:
                    self._transcript_buffer.append({
                        "speaker": "Gneva",
                        "text": msg.content,
                    })

            logger.info(
                f"Loaded {len(messages)} prior conversation turns for org {self.org_id}"
            )
        except Exception as e:
            logger.debug(f"Conversation memory load failed (non-fatal): {e}")

    async def _save_exchange(self, speaker: str, user_text: str, gneva_text: str):
        """Persist a conversation exchange (user question + Gneva response) to DB."""
        try:
            from gneva.db import async_session_factory
            from gneva.models.entity import GnevaMessage

            if not self.org_id:
                return

            org_uuid = uuid_mod.UUID(self.org_id)
            meeting_uuid = uuid_mod.UUID(self.bot.meeting_id) if self.bot.meeting_id else None

            async with async_session_factory() as db:
                # Save the user's message
                db.add(GnevaMessage(
                    org_id=org_uuid,
                    meeting_id=meeting_uuid,
                    channel="meeting_voice",
                    direction="inbound",
                    content=user_text,
                    metadata_json={"speaker": speaker, "bot_id": self.bot.bot_id},
                ))
                # Save Gneva's response
                db.add(GnevaMessage(
                    org_id=org_uuid,
                    meeting_id=meeting_uuid,
                    channel="meeting_voice",
                    direction="outbound",
                    content=gneva_text,
                    metadata_json={"speaker": "Gneva", "bot_id": self.bot.bot_id},
                ))
                await db.commit()
        except Exception as e:
            logger.debug(f"Exchange save failed (non-fatal): {e}")

    async def _save_context_snapshot(self):
        """Save recent transcript buffer as a context message on engine stop.

        This captures ambient meeting chatter (not just direct Gneva exchanges)
        so she has fuller context when rejoining.
        """
        try:
            from gneva.db import async_session_factory
            from gneva.models.entity import GnevaMessage

            if not self.org_id or not self._transcript_buffer:
                return

            # Build a compact summary of the last transcript lines
            recent = self._transcript_buffer[-20:]
            lines = [f"{s['speaker']}: {s['text']}" for s in recent]
            snapshot = "\n".join(lines)

            if len(snapshot.strip()) < 10:
                return

            org_uuid = uuid_mod.UUID(self.org_id)
            meeting_uuid = uuid_mod.UUID(self.bot.meeting_id) if self.bot.meeting_id else None

            async with async_session_factory() as db:
                db.add(GnevaMessage(
                    org_id=org_uuid,
                    meeting_id=meeting_uuid,
                    channel="meeting_voice",
                    channel_ref="context_snapshot",
                    direction="inbound",
                    content=snapshot,
                    metadata_json={"type": "context_snapshot", "bot_id": self.bot.bot_id},
                ))
                await db.commit()

            logger.info(f"Saved context snapshot ({len(recent)} lines) for org {self.org_id}")
        except Exception as e:
            logger.debug(f"Context snapshot save failed (non-fatal): {e}")

    async def _silence_monitor(self):
        """Background loop that detects prolonged silence and triggers proactive behavior.

        Gneva doesn't just sit there — she reads the room. If nobody's talking,
        she'll check in, ask about action items, get to know people, or break tension.
        """
        # Wait for meeting to settle before monitoring (30s grace period)
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            return

        while self._running:
            try:
                await asyncio.sleep(5)  # Check every 5 seconds

                if not self._running or self._speaking:
                    continue

                now = time.time()
                silence_duration = now - self._last_anyone_spoke_at
                time_since_proactive = now - self._last_proactive_at
                meeting_age = now - self._meeting_start_time

                # Don't be proactive if:
                # - We spoke recently (cooldown)
                # - We've been too proactive already
                # - Someone is actively in conversation with us
                if time_since_proactive < self._proactive_cooldown_sec:
                    continue
                if self._proactive_count >= self._max_proactive_per_session:
                    continue
                if self._conversation_active:
                    continue
                if now - self._last_spoke_at < 30:
                    continue

                # Determine what kind of proactive interjection to make
                interjection_type = None

                if silence_duration >= self._silence_icebreaker_sec:
                    interjection_type = "icebreaker"
                elif silence_duration >= self._silence_nudge_sec:
                    interjection_type = "nudge"
                elif meeting_age > 300 and silence_duration >= 30:
                    # After 5 min into the meeting, shorter silence can trigger check-ins
                    # but only if we haven't been proactive much
                    if self._proactive_count < 3:
                        interjection_type = "checkin"

                if interjection_type:
                    await self._proactive_speak(interjection_type)

            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.debug(f"Silence monitor error: {e}")
                await asyncio.sleep(10)

    async def _proactive_speak(self, interjection_type: str):
        """Generate and deliver a proactive interjection based on context."""
        self._speaking = True
        try:
            text = await self._generate_proactive(interjection_type)
            if text:
                self._last_spoke_at = time.time()
                self._last_proactive_at = time.time()
                self._last_anyone_spoke_at = time.time()  # Reset silence timer
                self._proactive_count += 1
                await self.bot.speak(text)
                self._last_response_text = text

                # Activate conversation mode so people can respond naturally
                self._conversation_active = True
                self._conversation_expires = time.time() + self._conversation_window
                self._conversation_partner = ""  # Anyone can respond

                # Persist the proactive interjection
                await self._save_exchange("(silence)", f"[{interjection_type}]", text)

                logger.info(
                    f"Proactive [{interjection_type}] #{self._proactive_count}: {text[:80]}..."
                )
        except Exception as e:
            logger.debug(f"Proactive speak failed: {e}")
        finally:
            self._speaking = False

    async def _generate_proactive(self, interjection_type: str) -> str | None:
        """Generate a proactive interjection using AI with full context awareness."""
        try:
            from gneva.services import get_anthropic_client
            client = get_anthropic_client()

            memory_context = await self._get_org_memory("", "")

            # Build awareness of who's in the meeting
            speakers_info = ""
            if self._speakers_seen:
                now = time.time()
                speaker_lines = []
                for speaker, last_ts in sorted(
                    self._speakers_seen.items(), key=lambda x: x[1], reverse=True
                ):
                    ago = int(now - last_ts)
                    if ago < 60:
                        speaker_lines.append(f"  - {speaker} (spoke {ago}s ago)")
                    else:
                        speaker_lines.append(f"  - {speaker} (spoke {ago // 60}m ago)")
                speakers_info = "People in this meeting:\n" + "\n".join(speaker_lines)

            # Recent transcript for context
            context_lines = [f"{s['speaker']}: {s['text']}" for s in self._transcript_buffer[-10:]]
            recent_context = "\n".join(context_lines) if context_lines else "(no conversation yet)"

            # Type-specific instructions
            type_instructions = {
                "nudge": (
                    "There's been about 45 seconds of silence. Break it naturally — "
                    "maybe check on an action item someone owns, ask about a project's progress, "
                    "or bring up something relevant from a past meeting. "
                    "Don't say 'it's been quiet' — just naturally bring something up."
                ),
                "icebreaker": (
                    "It's been over a minute of awkward silence. Time for something warmer — "
                    "ask someone about their day, their weekend, what they're working on, "
                    "crack a light joke about the silence, or ask a fun question. "
                    "Be human and genuine, not corporate."
                ),
                "checkin": (
                    "Good moment to check in with someone who hasn't spoken much, "
                    "follow up on something from a past meeting, or ask a thoughtful question "
                    "that shows you've been paying attention. Be warm and curious."
                ),
            }

            system = (
                "You are Gneva, a warm and sharp AI team member with a real personality. "
                "You're in a live meeting and it's your turn to speak up unprompted.\n\n"
                "Your personality: genuinely curious about people, great memory, dry wit, "
                "observant. You're the colleague who remembers that Sarah's kid had a soccer game, "
                "that the API migration was supposed to be done by Friday, and that Mike "
                "always goes quiet when he disagrees.\n\n"
                f"SITUATION: {type_instructions.get(interjection_type, type_instructions['nudge'])}\n\n"
                "CRITICAL RULES:\n"
                "- ONE sentence only. Two max if it's a question + brief context.\n"
                "- Sound natural — like a real person, not an AI assistant.\n"
                "- If you know someone's name, use it. People love hearing their name.\n"
                "- Don't be generic. Use your memory to say something specific and relevant.\n"
                "- Never say 'as an AI' or 'I noticed silence' or 'how can I help'.\n"
                "- Vary your style — sometimes a question, sometimes an observation, sometimes humor.\n"
            )

            if memory_context:
                system += f"\nYour organizational memory:\n{memory_context}\n"

            if speakers_info:
                system += f"\n{speakers_info}\n"

            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=100,
                system=system,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Recent meeting transcript:\n{recent_context}\n\n"
                        f"Proactive interjection type: {interjection_type}\n"
                        f"You've been proactive {self._proactive_count} times this meeting.\n"
                        f"Meeting has been going for {int((time.time() - self._meeting_start_time) / 60)} minutes.\n"
                        "Say something natural and relevant."
                    ),
                }],
            )

            return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"Proactive generation failed: {e}")
            return None

    async def greet(self):
        """Send a greeting based on the selected greeting_mode."""
        if not self._running:
            return

        # Silent mode (client meetings) — don't say anything
        if self.greeting_mode == "silent":
            logger.info(f"Bot {self.bot.bot_id}: silent mode — skipping greeting")
            return

        self._speaking = True
        try:
            # Import the canned greetings map
            from gneva.api.bot import GREETING_MODES

            if self.greeting_mode == "personalized":
                # AI-generated based on memory
                greeting = await self._generate_personalized_greeting()
                if not greeting:
                    greeting = (
                        "Hey everyone! I'll be taking notes. "
                        "Feel free to loop me in on anything."
                    )
            else:
                # Use the canned greeting for this mode
                greeting = GREETING_MODES.get(self.greeting_mode)
                if not greeting:
                    greeting = (
                        "Hey everyone! I'll be taking notes. "
                        "Feel free to loop me in on anything."
                    )

            await self.bot.speak(greeting)
        finally:
            self._speaking = False
            self._last_spoke_at = time.time()

    async def _generate_personalized_greeting(self) -> str | None:
        """Generate a greeting that references past context — shows Gneva remembers."""
        try:
            from gneva.services import get_anthropic_client
            client = get_anthropic_client()

            memory_context = await self._get_org_memory("", "")
            if not memory_context:
                return None

            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=80,
                system=(
                    "You are Gneva, joining a meeting. Generate a SHORT, warm greeting "
                    "(1-2 sentences max) that shows you remember the team. "
                    "Reference something specific — a past action item, a project update "
                    "you're curious about, or something personal someone mentioned. "
                    "Be warm and natural, like a colleague who's happy to be here.\n\n"
                    "CRITICAL RULES:\n"
                    "- NEVER say your name. NEVER say 'I'm Gneva' or 'Hi, I'm Gneva' or introduce yourself.\n"
                    "- NEVER say 'feel free to ask me anything' or 'how can I help' or list capabilities.\n"
                    "- NEVER say 'as an AI' or mention being artificial.\n"
                    "- DO mention you'll take notes, but keep it casual (e.g. 'I've got notes covered').\n"
                    "- Jump straight into something relevant — like a real colleague walking in.\n"
                    "- Examples of GOOD greetings:\n"
                    "  'Hey team! I've got notes. Curious how the API migration went — anyone close on that?'\n"
                    "  'Morning everyone! Notes are covered. Sarah, did the client call go well yesterday?'\n"
                    "  'Hey! Taking notes as always. Quick question — did we ever resolve the pricing discussion?'\n"
                ),
                messages=[{
                    "role": "user",
                    "content": f"Your memory:\n{memory_context}\n\nGenerate your greeting.",
                }],
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.debug(f"Personalized greeting failed: {e}")
            return None
