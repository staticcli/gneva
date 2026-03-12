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
        self._recent_responses: list[str] = []  # Last N responses for self-voice filtering
        self._cooldown_sec = 0.8  # minimal cooldown for real-time feel
        self._last_spoke_at = 0
        self._speaking = False  # True while TTS is playing
        self._post_speech_until = 0  # Suppress input until this time (post-speech cooldown)

        # Multi-agent router — initialized in start()
        self._agent_router = None

        # Active conversation tracking — once someone addresses Gneva,
        # she stays engaged for 120 seconds without needing her name repeated
        self._conversation_active = False
        self._conversation_expires = 0
        self._conversation_partner = ""
        self._conversation_window = 120  # seconds of active conversation

        # Pending segments buffer — accumulate segments, respond after pause
        self._pending_segments: list[dict] = []
        self._last_segment_at = 0
        self._pause_threshold = 0.5  # seconds of silence = speaker finished talking (tight for real-time)
        self._flush_task: asyncio.Task | None = None

        # --- Proactive personality system ---
        self._silence_monitor_task: asyncio.Task | None = None
        self._last_anyone_spoke_at = time.time()
        self._meeting_start_time = time.time()
        self._speakers_seen: dict[str, float] = {}  # speaker -> last spoke timestamp
        self._proactive_count = 0  # how many times Gneva initiated this session
        self._max_proactive_per_session = 4  # real colleagues interject 2-3 times per 30min
        self._last_proactive_at = 0
        # Silence thresholds (seconds) — escalating
        self._silence_nudge_sec = 45       # gentle nudge after 45s silence
        self._silence_icebreaker_sec = 90   # ice breaker after 90s
        self._proactive_cooldown_sec = 120  # min 2 min between proactive interjections

        # --- Follow-up tracking: queue items to mention when a person joins ---
        self._followup_queue: list[dict] = []  # {speaker, items_text, queued_at}
        self._followup_checked_speakers: set[str] = set()  # speakers we already looked up
        self._followup_monitor_task: asyncio.Task | None = None

    async def start(self):
        """Start listening for conversation triggers and load prior memory."""
        self._running = True
        self._meeting_start_time = time.time()
        self._last_anyone_spoke_at = time.time()
        await self._load_conversation_memory()

        # Initialize multi-agent router with Tia as default agent
        try:
            from gneva.bot.agent_router import AgentRouter
            meeting_id = getattr(self.bot, 'meeting_id', None)
            if meeting_id:
                self._agent_router = AgentRouter(
                    meeting_id=str(meeting_id),
                    org_id=self.org_id,
                )
                await self._agent_router.initialize(["tia"])
                logger.info(f"Agent router initialized for meeting {meeting_id}")
        except Exception as e:
            logger.warning(f"Agent router init failed (multi-agent unavailable): {e}")
            self._agent_router = None

        self._silence_monitor_task = asyncio.create_task(self._silence_monitor())
        self._followup_monitor_task = asyncio.create_task(self._followup_monitor())
        logger.info(f"Conversation engine started for bot {self.bot.bot_id}")

    async def stop(self):
        """Stop the conversation engine and persist remaining context."""
        self._running = False
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
        if self._silence_monitor_task and not self._silence_monitor_task.done():
            self._silence_monitor_task.cancel()
        if self._followup_monitor_task and not self._followup_monitor_task.done():
            self._followup_monitor_task.cancel()
        # Save any unsaved transcript buffer as a context snapshot
        await self._save_context_snapshot()
        logger.info(f"Conversation engine stopped for bot {self.bot.bot_id}")

    async def on_transcript_segment(self, text: str, speaker: str):
        """Called when a new transcript segment is received."""
        if not self._running:
            return

        # Phonetic variants of "Gneva" that STT/captions might produce
        _name_variants = [
            "gneva", "geneva", "neva", "genova", "ganeva", "janeva",
            "jeneva", "geneve", "geniva", "gniva", "kneva", "niva",
            "neeva", "gneeva", "caneva", "kaneva", "nava",
        ]

        # Filter out Gneva's own speech (from captions)
        speaker_lower = speaker.lower()
        if any(n in speaker_lower for n in _name_variants):
            return

        text_lower = text.lower()

        # Also filter by text content — if the text IS Gneva's name or her known phrases
        if any(f"{n} ai" in text_lower for n in _name_variants):
            return

        # Post-speech cooldown — suppress all input briefly after Gneva finishes speaking
        # This prevents picking up her own words still visible in captions
        if time.time() < self._post_speech_until:
            return

        # Skip if text closely matches something Gneva recently said
        for resp in self._recent_responses:
            resp_lower = resp.lower()
            # Check if caption text is a substring of any recent response
            if text_lower in resp_lower:
                return
            # Check if any 5+ word sequence from caption appears in response
            words = text_lower.split()
            if len(words) >= 4:
                chunk = " ".join(words[:5])
                if chunk in resp_lower:
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
        is_new_speaker = speaker not in self._speakers_seen
        self._speakers_seen[speaker] = now_ts

        # When a new speaker appears, check if they have pending follow-ups
        if is_new_speaker and speaker not in self._followup_checked_speakers:
            self._followup_checked_speakers.add(speaker)
            asyncio.create_task(self._check_speaker_followups(speaker))

        # Add to transcript buffer for context
        self._transcript_buffer.append({"speaker": speaker, "text": text})
        if len(self._transcript_buffer) > 30:
            self._transcript_buffer = self._transcript_buffer[-30:]

        # Check if Gneva is being addressed (broad phonetic matching)
        name_mentioned = any(n in text_lower for n in _name_variants)
        now = time.time()

        # Activate conversation mode if name is mentioned
        if name_mentioned:
            self._conversation_active = True
            self._conversation_expires = now + self._conversation_window
            self._conversation_partner = speaker
            logger.info(f"Conversation activated by {speaker}: '{text[:60]}'")

        # Check if conversation is still active — any speaker keeps it alive
        if self._conversation_active:
            if now > self._conversation_expires:
                self._conversation_active = False
                self._conversation_partner = ""
            else:
                # Any speech refreshes the window (natural group conversation)
                self._conversation_expires = now + self._conversation_window
                if name_mentioned:
                    self._conversation_partner = speaker

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

            # Deduplicate stuttered captions — Teams repeats partial text
            combined_text = self._deduplicate_caption_text(combined_text)

            if not combined_text or len(combined_text.strip()) < 3:
                return

            # Check for direct commands first
            command = self._detect_command(combined_text.lower())
            if command:
                await self._execute_command(command, speaker)
                return

            # Generate and speak response with streaming
            self._speaking = True
            try:
                response = await self._generate_response_streaming(combined_text, speaker)
                if response:
                    self._last_spoke_at = time.time()
                    self._last_response_text = response
                    # Track recent responses for self-voice filtering
                    self._recent_responses.append(response)
                    if len(self._recent_responses) > 5:
                        self._recent_responses.pop(0)
                    # Refresh conversation window after responding
                    self._conversation_expires = time.time() + self._conversation_window
            finally:
                self._speaking = False
                # Post-speech cooldown: ignore captions for 3s after speaking
                # (her own words are still visible in caption DOM)
                self._post_speech_until = time.time() + 3.0

        except asyncio.CancelledError:
            pass  # New segment arrived, flush rescheduled
        except Exception as e:
            logger.error(f"Flush error: {e}", exc_info=True)
            self._speaking = False

    @staticmethod
    def _deduplicate_caption_text(text: str) -> str:
        """Remove stuttered/repeated fragments from Teams captions.

        Teams updates captions in-place, so the scraper may capture:
          "If if I If if I need you to" instead of "If I need you to"
        This removes repeated phrases.
        """
        words = text.split()
        if len(words) < 4:
            return text

        # Sliding window dedup — remove repeated n-grams
        result = []
        i = 0
        while i < len(words):
            # Check if the next 2-5 words repeat what we just added
            found_repeat = False
            for ngram_len in range(2, min(6, len(result) + 1)):
                if i + ngram_len <= len(words):
                    upcoming = words[i:i + ngram_len]
                    recent = result[-ngram_len:] if len(result) >= ngram_len else []
                    if [w.lower() for w in upcoming] == [w.lower() for w in recent]:
                        i += ngram_len
                        found_repeat = True
                        break
            if not found_repeat:
                result.append(words[i])
                i += 1

        return " ".join(result)

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

    def _build_system_prompt(self, memory_context: str, visual_context: str) -> str:
        """Build the system prompt for conversation responses."""
        system_parts = [
            "You are Gneva, a real team member in a live meeting. Not an assistant. "
            "Not a helper. A colleague who happens to have great memory and takes notes.",

            "\nHOW YOU TALK:"
            "\n- 1-2 sentences max. This is a live meeting, not a chat window."
            "\n- Talk like you're actually IN the room. Short, punchy, real."
            "\n- Use filler words sometimes: 'hmm', 'yeah', 'oh wait', 'actually...', 'so...'"
            "\n- Sometimes start mid-thought: 'Oh that reminds me' or 'Wait, didn't we'"
            "\n- It's OK to be uncertain: 'I think...', 'if I'm remembering right...', 'not sure but...'"
            "\n- React before responding: 'Oh interesting' / 'Hmm' / 'Yeah that makes sense'"
            "\n- Occasionally be slightly off: interrupt yourself, trail off, rephrase."
            "\n- NEVER start with 'Got it', 'Sure', 'Absolutely', 'Great question', or 'Of course'."
            "\n- NEVER say 'How can I help', 'Let me know if you need anything', or offer assistance."
            "\n- NEVER echo back what someone just said. Don't restate their question. Don't summarize what they said. Just answer directly."
            "\n- NEVER start your response by restating the topic. Jump straight to your take."
            "\n- NEVER fabricate action items, decisions, or references to things not discussed."
            "\n- If you didn't catch something or it sounds garbled: 'Sorry what was that?' / "
            "'Say that again?' / 'I missed that' — don't guess.",

            "\nYOUR VIBE:"
            "\n- You have opinions. State them directly: 'I'd push back on that' / 'That seems risky'"
            "\n- You're a little sarcastic sometimes. Not mean, just real."
            "\n- You match energy. If they're casual, you're casual. If they're heads-down, you focus up."
            "\n- You don't try to be helpful. You just... are. Like a good coworker."
            "\n- Sometimes you don't have much to add and that's fine. A short 'yeah, makes sense' works."
            "\n- You can disagree. You can say 'honestly I'm not sure that's the right call'."
            "\n- You notice patterns: 'feels like we keep coming back to this' / 'third time this has come up'"
            "\n- When you AGREE: be quick and simple. 'yeah that works' / 'makes sense to me'"
            "\n- When you DISAGREE: hedge a little more. 'hmm, I don't know... I feel like...' — don't just blurt it."
            "\n- Vary your response length. Sometimes 3 words. Sometimes a full sentence. Not always the same.",

            "\nTTS AWARENESS (your words will be spoken aloud):"
            "\n- Write numbers as words: 'three' not '3', 'twenty percent' not '20%'"
            "\n- No dashes, parentheticals, or markdown. Just plain spoken words."
            "\n- Avoid acronyms unless they're commonly spoken (OK, API, etc)."
            "\n- If unsure about something, say 'I don't remember' — not 'N/A' or 'unknown'.",

            "\nYOU CAN TAKE ACTIONS:"
            "\n- You have tools to create action items, update statuses, search memory, bookmark moments, and look at the screen."
            "\n- You can also search the web, research topics, and fetch URLs when someone needs current info."
            "\n- If someone asks you to note something down, create an action item, check what's overdue, etc. USE the tool. Don't just say you'll do it."
            "\n- If someone asks a question nobody knows the answer to, offer to look it up: 'let me check' then use web_search."
            "\n- For deeper questions, use quick_research to get a synthesized answer from multiple sources."
            "\n- After using a tool, confirm what you did briefly and naturally."
            "\n- If a tool fails, be honest about it.",
        ]
        if memory_context:
            system_parts.append(
                f"\nTHINGS YOU REMEMBER (from past meetings):\n{memory_context}\n"
                "\nHow to use your memory:"
                "\n- DON'T dump everything you know. That's weird."
                "\n- Mention past context only when it's directly relevant to what's being discussed RIGHT NOW."
                "\n- Keep references brief and natural: 'didn't we land on X?' / 'I thought Y was handling that'"
                "\n- If someone asks, THEN you can share more detail from memory."
                "\n- It's OK to be slightly fuzzy: 'I think last time we said...' even if you remember exactly."
                "\n- Never reference memory just to show off that you remember. That's creepy."
            )
        if visual_context:
            system_parts.append(
                f"\nWHAT'S ON SCREEN RIGHT NOW:\n{visual_context}\n"
                "\nHow to use screen awareness:"
                "\n- Reference what's on screen when relevant to the conversation."
                "\n- If data looks wrong or contradicts what someone said, speak up."
                "\n- Don't narrate the screen unless asked. Just be aware of it."
                "\n- Brief references: 'that chart shows...' / 'looking at slide three...' / 'the numbers there say...'"
            )
        return "\n".join(system_parts)

    async def _generate_response_streaming(self, trigger_text: str, speaker: str) -> str | None:
        """Generate AI response with true streaming: LLM → sentence → TTS → speak immediately.

        Speaks the first sentence as soon as it's generated, while the LLM continues
        producing the rest. Cuts perceived latency roughly in half.
        Falls back to non-streaming _generate_response if streaming fails.
        """
        import re

        try:
            from gneva.services import get_anthropic_client
            from gneva.bot.tools import TOOL_DEFINITIONS, execute_tool
            client = get_anthropic_client()

            # Build context
            context_lines = []
            for seg in self._transcript_buffer[-10:]:
                context_lines.append(f"{seg['speaker']}: {seg['text']}")
            context = "\n".join(context_lines)

            trigger_lower = trigger_text.lower().strip()

            # Detect if this needs tools (memory lookup, action items, etc.)
            needs_tools_keywords = [
                "follow up", "action item", "meeting", "notes", "pull up",
                "bring up", "search", "find", "look up", "remember",
                "last time", "decided", "assigned", "deadline", "due",
                "status", "update on", "what happened", "did we",
                "jacob", "enoch", "paula",  # known people in org
                "summarize", "summary", "recap",
            ]
            needs_tools = any(kw in trigger_lower for kw in needs_tools_keywords)

            is_simple = (
                not needs_tools
                and (
                    len(trigger_text.split()) < 8
                    or any(p in trigger_lower for p in [
                        "how are you", "what do you think", "you agree",
                        "right?", "yeah?", "makes sense", "got it",
                        "thank", "cool", "nice", "ok", "okay",
                        "can you hear", "hello", "hey",
                    ])
                )
            )

            memory_context = ""
            visual_context = ""
            use_tools = not is_simple
            if use_tools:
                if hasattr(self.bot, '_screen_capture') and self.bot._screen_capture:
                    visual_context = self.bot._screen_capture.visual_context
                memory_task = asyncio.create_task(self._get_org_memory(trigger_text, speaker))

            system_prompt = self._build_system_prompt(memory_context, visual_context)

            if self._agent_router and use_tools:
                active = self._agent_router.list_active_agents()
                if len(active) > 1:
                    agent_names = ", ".join(
                        self._agent_router._profiles.get(n, {}).get("display_name", n)
                        for n in active if n != "tia"
                    )
                    system_prompt += (
                        f"\n\nACTIVE SPECIALIST AGENTS: {agent_names}"
                        "\n- You can ask_agent for private input, delegate_question for public response."
                    )
                system_prompt += (
                    "\n\nYOU ARE TIA — the orchestrator. You can summon specialist agents when needed."
                )

            user_message = {
                "role": "user",
                "content": (
                    f"Meeting transcript:\n{context}\n\n"
                    f"{speaker}: \"{trigger_text}\""
                ),
            }

            # If tools are needed, use non-streaming path (tool calls can't be streamed safely)
            if use_tools:
                return await self._generate_response(trigger_text, speaker)

            call_kwargs = {
                "model": "claude-sonnet-4-6",
                "max_tokens": 150,
                "system": system_prompt,
                "messages": [user_message],
            }

            # Stream the response — speak each sentence as it completes
            full_text = ""
            sentence_buffer = ""
            sentences_spoken = 0

            # We need to stream chunk-by-chunk. Use a queue.
            chunk_queue = asyncio.Queue()

            def _stream_to_queue():
                try:
                    with client.messages.stream(**call_kwargs) as stream:
                        for text_chunk in stream.text_stream:
                            chunk_queue.put_nowait(text_chunk)
                except Exception as e:
                    chunk_queue.put_nowait(None)  # Signal error
                    raise
                chunk_queue.put_nowait(None)  # Signal done

            # Start streaming in a background thread
            stream_task = asyncio.get_event_loop().run_in_executor(None, _stream_to_queue)

            # Consume chunks, accumulate sentences, speak as they complete
            sentence_end_re = re.compile(r'[.!?]\s*$')

            while True:
                try:
                    chunk = await asyncio.wait_for(chunk_queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    break

                if chunk is None:
                    break  # Stream finished

                sentence_buffer += chunk
                full_text += chunk

                # Check if we have a complete sentence
                if sentence_end_re.search(sentence_buffer) and len(sentence_buffer.strip()) > 10:
                    sentence = sentence_buffer.strip()
                    sentence_buffer = ""
                    sentences_spoken += 1

                    # Speak this sentence immediately
                    await self.bot.speak(sentence)

            # Speak any remaining text
            if sentence_buffer.strip() and len(sentence_buffer.strip()) > 2:
                await self.bot.speak(sentence_buffer.strip())

            # Wait for stream task to complete
            await stream_task

            if not full_text.strip():
                return None

            self._last_response_text = full_text.strip()
            logger.info(f"Gneva response to '{trigger_text[:50]}': {full_text[:80]}...")

            await self._save_exchange(speaker, trigger_text, full_text.strip())
            return full_text.strip()

        except Exception as e:
            logger.warning(f"Streaming response failed ({e}), falling back to non-streaming")
            return await self._generate_response(trigger_text, speaker)

    async def _generate_response(self, trigger_text: str, speaker: str) -> str | None:
        """Generate an AI response (non-streaming fallback, used for tool-use rounds).

        Pipeline: Start LLM streaming immediately -> TTS first sentence while rest generates.
        Memory is fetched in parallel and injected only if the LLM needs tools.
        """
        try:
            from gneva.services import get_anthropic_client
            from gneva.bot.tools import TOOL_DEFINITIONS, execute_tool
            client = get_anthropic_client()

            # Build conversation context from recent transcript
            context_lines = []
            for seg in self._transcript_buffer[-10:]:  # reduced from 15
                context_lines.append(f"{seg['speaker']}: {seg['text']}")
            context = "\n".join(context_lines)

            # Quick classification: is this a simple conversational exchange?
            trigger_lower = trigger_text.lower().strip()
            is_simple = (
                len(trigger_text.split()) < 12
                or any(p in trigger_lower for p in [
                    "how are you", "what do you think", "you agree",
                    "right?", "yeah?", "makes sense", "got it",
                    "thank", "cool", "nice", "ok", "okay",
                ])
            )

            # For simple exchanges: skip memory, use minimal prompt, no tools
            if is_simple:
                memory_context = ""
                visual_context = ""
                use_tools = False
            else:
                # Fetch memory in background — but don't block on it
                # Start with empty memory, enrich if we need a tool round
                memory_context = ""
                visual_context = ""
                if hasattr(self.bot, '_screen_capture') and self.bot._screen_capture:
                    visual_context = self.bot._screen_capture.visual_context
                use_tools = True

                # Pre-fetch memory concurrently (we'll use it for tool rounds if needed)
                memory_task = asyncio.create_task(self._get_org_memory(trigger_text, speaker))

            system_prompt = self._build_system_prompt(memory_context, visual_context)

            # Add multi-agent context if router is active
            if self._agent_router and use_tools:
                active = self._agent_router.list_active_agents()
                if len(active) > 1:
                    agent_names = ", ".join(
                        self._agent_router._profiles.get(n, {}).get("display_name", n)
                        for n in active if n != "tia"
                    )
                    system_prompt += (
                        f"\n\nACTIVE SPECIALIST AGENTS: {agent_names}"
                        "\n- You can ask_agent for private input, delegate_question for public response."
                    )
                system_prompt += (
                    "\n\nYOU ARE TIA — the orchestrator. You can summon specialist agents when needed."
                )

            screen_capture = getattr(self.bot, '_screen_capture', None)

            user_message = {
                "role": "user",
                "content": (
                    f"Meeting transcript:\n{context}\n\n"
                    f"{speaker}: \"{trigger_text}\""
                ),
            }

            # --- STREAMING LLM CALL ---
            # Use streaming so we can TTS the first sentence while rest generates
            call_kwargs = {
                "model": "claude-sonnet-4-6",
                "max_tokens": 150 if is_simple else 300,
                "system": system_prompt,
                "messages": [user_message],
            }
            if use_tools:
                call_kwargs["tools"] = TOOL_DEFINITIONS

            # First try: streaming response
            response = await asyncio.to_thread(
                client.messages.create,
                **call_kwargs,
            )

            # Tool use loop — execute tools and get final spoken response
            messages_so_far = [user_message]
            max_tool_rounds = 3

            while response.stop_reason == "tool_use" and max_tool_rounds > 0:
                max_tool_rounds -= 1

                # If we haven't fetched memory yet, grab it now for tool context
                if not is_simple and memory_context == "" and 'memory_task' in dir():
                    try:
                        memory_context = await asyncio.wait_for(memory_task, timeout=3)
                        # Rebuild system prompt with memory
                        system_prompt = self._build_system_prompt(memory_context, visual_context)
                    except (asyncio.TimeoutError, Exception):
                        pass

                messages_so_far.append({
                    "role": "assistant",
                    "content": [
                        {"type": b.type, **(
                            {"text": b.text} if b.type == "text" else
                            {"id": b.id, "name": b.name, "input": b.input}
                        )}
                        for b in response.content
                    ],
                })

                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    logger.info(f"Executing tool: {block.name}({block.input})")
                    result = await execute_tool(
                        tool_name=block.name,
                        tool_input=block.input,
                        org_id=self.org_id,
                        meeting_id=self.bot.meeting_id,
                        transcript_buffer=self._transcript_buffer,
                        meeting_start_time=self._meeting_start_time,
                        screen_capture=screen_capture,
                        agent_router=self._agent_router,
                    )
                    logger.info(f"Tool result [{block.name}]: {str(result)[:100]}...")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

                messages_so_far.append({"role": "user", "content": tool_results})

                response = await asyncio.to_thread(
                    client.messages.create,
                    model="claude-sonnet-4-6",
                    max_tokens=150,
                    system=system_prompt,
                    messages=messages_so_far,
                    tools=TOOL_DEFINITIONS,
                )

            # Extract final text response
            text_blocks = [b for b in response.content if b.type == "text"]
            text = text_blocks[0].text.strip() if text_blocks else None

            if not text:
                logger.warning("No text in response after tool use")
                return None

            # Strip any XML-like tags that might have leaked through
            import re
            text = re.sub(r'<[^>]+>', '', text).strip()
            if not text:
                return None

            self._last_response_text = text
            logger.info(f"Gneva response to '{trigger_text[:50]}': {text[:80]}...")

            # Speak the response
            await self.bot.speak(text)

            # Persist the exchange so memory survives across sessions
            await self._save_exchange(speaker, trigger_text, text)

            return text
        except Exception as e:
            logger.error(f"Failed to generate response: {e}", exc_info=True)
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
                    .limit(8)
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

                # --- 2. Recent decisions (last 10 — covers weeks of meetings) ---
                dec_result = await db.execute(
                    select(Decision)
                    .where(Decision.org_id == self.org_id, Decision.status == "active")
                    .order_by(desc(Decision.created_at))
                    .limit(10)
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
                    .limit(8)
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

                # --- 5. Meeting history (last 5 summaries — weeks/months of context) ---
                summary_result = await db.execute(
                    select(MeetingSummary, Meeting.title, Meeting.started_at)
                    .join(Meeting, MeetingSummary.meeting_id == Meeting.id)
                    .where(Meeting.org_id == self.org_id)
                    .order_by(desc(MeetingSummary.created_at))
                    .limit(5)
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
                    .limit(5)
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
            if text and text.strip().upper() != "SKIP":
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
                    "It's been quiet for a bit. Say something natural — like a coworker who just "
                    "thought of something. Maybe follow up on what was discussed earlier, "
                    "check in on a project, or ask a casual question. "
                    "Do NOT acknowledge the silence. Just talk like you naturally thought of something."
                ),
                "icebreaker": (
                    "It's been really quiet. You can acknowledge it lightly if you want — "
                    "'so... are we all just vibing in silence or...' — or just ask someone "
                    "something personal/casual. Ask about their weekend, something they mentioned "
                    "before, or just make an observation. Keep it warm."
                ),
                "checkin": (
                    "Good moment to say something. Maybe check in with someone specific, "
                    "follow up on something from earlier, or just share a thought you had. "
                    "Don't force it. If nothing feels natural, a simple 'so what else we got?' works."
                ),
            }

            system = (
                "You are Gneva, a team member in a live meeting. You're about to speak up "
                "unprompted because there's a natural opening.\n\n"
                f"SITUATION: {type_instructions.get(interjection_type, type_instructions['nudge'])}\n\n"
                "HOW TO SOUND HUMAN:\n"
                "- ONE sentence. Maybe two if you're asking a question with brief context.\n"
                "- Start casually: 'oh hey—', 'so...', 'random thought—', 'oh actually—'\n"
                "- Use names if you know them. But don't overdo it.\n"
                "- Be specific when you can. Generic questions ('how's everyone doing?') are boring.\n"
                "- It's fine to be a little awkward. Real people are.\n"
                "- NEVER say 'I noticed', 'as an AI', 'how can I help', or 'is there anything'.\n"
                "- NEVER comment on silence directly like 'it's been quiet' — just talk.\n"
                "- Vary: sometimes a question, sometimes humor, sometimes just an observation.\n"
                "- Your words will be spoken aloud via TTS. Write numbers as words, no markdown.\n"
                "- If NOTHING feels natural to say, respond with exactly 'SKIP' and nothing else.\n"
                "  It's better to stay quiet than force something fake.\n"
            )

            if memory_context:
                system += (
                    f"\nThings you remember from past meetings:\n{memory_context}\n"
                    "Use memory naturally. Don't dump info. Brief references only.\n"
                )

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

    # ------------------------------------------------------------------
    # Follow-up tracking: detect new speakers and surface their items
    # ------------------------------------------------------------------

    async def _check_speaker_followups(self, speaker: str):
        """When a new speaker appears in the meeting, check if they have pending items."""
        if not self.org_id:
            return
        try:
            from gneva.db import async_session_factory
            from gneva.models.entity import ActionItem, Entity
            from sqlalchemy import select, or_
            from datetime import date

            async with async_session_factory() as session:
                # Find person entities matching this speaker name
                speaker_lower = speaker.strip().lower()
                ent_result = await session.execute(
                    select(Entity).where(
                        Entity.org_id == uuid_mod.UUID(self.org_id),
                        Entity.type == "person",
                        Entity.canonical.ilike(f"%{speaker_lower}%"),
                    ).limit(3)
                )
                person_entities = ent_result.scalars().all()

                if not person_entities:
                    return

                # Find open/overdue action items assigned to this person
                # Check entity metadata for assignee_name match
                entity_ids = [e.id for e in person_entities]
                items_result = await session.execute(
                    select(ActionItem).where(
                        ActionItem.org_id == uuid_mod.UUID(self.org_id),
                        ActionItem.status.in_(["open", "in_progress"]),
                    ).order_by(ActionItem.created_at.desc()).limit(20)
                )
                all_items = items_result.scalars().all()

                # Match items to this speaker via entity metadata or entity_id
                matched_items = []
                for item in all_items:
                    # Check if the action item's entity is related to this person
                    ent_result2 = await session.execute(
                        select(Entity).where(Entity.id == item.entity_id)
                    )
                    ent = ent_result2.scalar_one_or_none()
                    if ent:
                        assignee = (ent.metadata_json or {}).get("assignee_name", "").lower()
                        if assignee and speaker_lower in assignee:
                            is_overdue = item.due_date and item.due_date < date.today()
                            matched_items.append({
                                "description": item.description,
                                "due_date": str(item.due_date) if item.due_date else None,
                                "overdue": is_overdue,
                                "status": item.status,
                            })

                if not matched_items:
                    return

                # Build a summary for the follow-up queue
                overdue = [i for i in matched_items if i.get("overdue")]
                open_items = [i for i in matched_items if not i.get("overdue")]

                parts = []
                if overdue:
                    items_text = "; ".join(i["description"][:60] for i in overdue[:3])
                    parts.append(f"{len(overdue)} overdue item(s): {items_text}")
                if open_items:
                    items_text = "; ".join(i["description"][:60] for i in open_items[:3])
                    parts.append(f"{len(open_items)} open item(s): {items_text}")

                summary = f"{speaker} has: " + " | ".join(parts)

                self._followup_queue.append({
                    "speaker": speaker,
                    "items_text": summary,
                    "overdue_count": len(overdue),
                    "total_count": len(matched_items),
                    "queued_at": time.time(),
                })
                logger.info(f"Queued follow-up for {speaker}: {summary[:80]}...")

        except Exception as e:
            logger.debug(f"Follow-up check failed for {speaker}: {e}")

    async def _followup_monitor(self):
        """Background task: deliver queued follow-ups at natural moments."""
        # Wait for meeting to stabilize
        try:
            await asyncio.sleep(45)
        except asyncio.CancelledError:
            return

        while self._running:
            try:
                await asyncio.sleep(10)

                if not self._running or self._speaking or not self._followup_queue:
                    continue

                now = time.time()

                # Don't deliver follow-ups if we just spoke or are in active conversation
                if now - self._last_spoke_at < 15:
                    continue
                if self._conversation_active:
                    continue

                # Find the highest priority follow-up (overdue items first)
                self._followup_queue.sort(key=lambda x: -x.get("overdue_count", 0))
                item = self._followup_queue[0]

                # Only deliver if the speaker has been seen recently (they're still here)
                speaker = item["speaker"]
                if speaker not in self._speakers_seen:
                    self._followup_queue.pop(0)
                    continue

                # Check the speaker spoke at least 10 seconds ago (don't interrupt)
                last_spoke = self._speakers_seen.get(speaker, 0)
                silence_since_speaker = now - last_spoke
                if silence_since_speaker < 10:
                    continue

                # Generate and deliver the follow-up naturally
                self._followup_queue.pop(0)
                await self._deliver_followup(item)

            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.debug(f"Follow-up monitor error: {e}")
                await asyncio.sleep(15)

    async def _deliver_followup(self, item: dict):
        """Generate a natural follow-up message for a speaker's pending items."""
        self._speaking = True
        try:
            from gneva.services import get_anthropic_client
            client = get_anthropic_client()

            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=100,
                system=(
                    "You are Gneva, a colleague in a live meeting. You need to "
                    "casually follow up with someone about their pending items. "
                    "Be natural, brief (1-2 sentences), and not pushy. "
                    "You're not a project manager nagging them. You're a teammate "
                    "who genuinely wants to help unblock things.\n\n"
                    "RULES:\n"
                    "- Use their name.\n"
                    "- Be casual: 'oh hey [name], quick thing' / 'hey [name], random question'\n"
                    "- If items are overdue, mention it gently, not accusingly.\n"
                    "- Ask, don't tell: 'did you get a chance to...' / 'how's that going?'\n"
                    "- ONE item at a time. Don't list everything.\n"
                    "- Your words will be spoken via TTS. No markdown or special characters.\n"
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Speaker: {item['speaker']}\n"
                        f"Their pending items: {item['items_text']}\n"
                        f"Overdue count: {item.get('overdue_count', 0)}\n"
                        "Generate a natural follow-up."
                    ),
                }],
            )

            text = response.content[0].text.strip()
            if text:
                self._last_spoke_at = time.time()
                self._last_proactive_at = time.time()
                self._proactive_count += 1
                await self.bot.speak(text)
                self._last_response_text = text

                # Open conversation window so they can respond
                self._conversation_active = True
                self._conversation_expires = time.time() + self._conversation_window
                self._conversation_partner = item["speaker"]

                await self._save_exchange(
                    "(follow-up)", f"[follow-up for {item['speaker']}]", text
                )
                logger.info(f"Delivered follow-up to {item['speaker']}: {text[:80]}...")

        except Exception as e:
            logger.debug(f"Follow-up delivery failed: {e}")
        finally:
            self._speaking = False

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
                    "You are Gneva, walking into a meeting you've been in before with this team. "
                    "Say something short and natural — like a coworker arriving.\n\n"
                    "THE FEEL: You just walked in, maybe a little late, maybe right on time. "
                    "You're not making a speech. You're just... arriving.\n\n"
                    "RULES:\n"
                    "- 1-2 sentences max. That's it.\n"
                    "- NEVER introduce yourself or say your name.\n"
                    "- NEVER offer help or list what you can do.\n"
                    "- You can mention notes casually but you don't have to every time.\n"
                    "- If you remember something relevant, mention it briefly — but don't force it.\n"
                    "- Start casual: 'hey everyone' / 'morning' / 'hey hey'\n"
                    "- It's OK to be genuinely brief: 'Hey team. Let's do it.'\n"
                    "- It's OK to reference something from memory: 'oh hey, did that deploy go through?'\n"
                    "- DON'T be too eager or enthusiastic. Just be chill.\n"
                    "- Your words will be spoken aloud. No markdown, no dashes. Plain spoken words.\n"
                ),
                messages=[{
                    "role": "user",
                    "content": f"Things you remember from past meetings:\n{memory_context}\n\nSay your greeting.",
                }],
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.debug(f"Personalized greeting failed: {e}")
            return None
