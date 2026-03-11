"""Real-time conversation engine — listens to meeting audio, responds via TTS.

Flow: Live captions → Buffer segments → Detect pause → AI response → TTS → Lip-sync
"""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class ConversationEngine:
    """Manages real-time conversation for a bot in a meeting.

    Key design:
    - Buffers incoming caption segments and waits for a speech pause before responding
    - Maintains "active conversation" mode so users don't have to say "Gneva" every time
    - Filters out Gneva's own captions and system messages
    - Short cooldown (3s) to allow natural back-and-forth
    """

    def __init__(self, bot, org_id: str | None = None):
        self.bot = bot
        self.org_id = org_id
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
        self._pause_threshold = 1.8  # seconds of silence = speaker finished talking
        self._flush_task: asyncio.Task | None = None

    async def start(self):
        """Start listening for conversation triggers."""
        self._running = True
        logger.info(f"Conversation engine started for bot {self.bot.bot_id}")

    async def stop(self):
        """Stop the conversation engine."""
        self._running = False
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
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
        """Generate an AI response to the conversation."""
        try:
            from gneva.services import get_anthropic_client
            client = get_anthropic_client()

            # Build conversation context from recent transcript
            context_lines = []
            for seg in self._transcript_buffer[-15:]:
                context_lines.append(f"{seg['speaker']}: {seg['text']}")
            context = "\n".join(context_lines)

            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-sonnet-4-6",
                max_tokens=150,
                system=(
                    "You are Gneva, a sharp AI team member in a live meeting. "
                    "You speak naturally like a real colleague.\n"
                    "CRITICAL: Keep responses to 1-2 SHORT sentences max. "
                    "You're speaking out loud in a meeting — be punchy, not verbose. "
                    "Never give a monologue. If you need to say more, give the key point and let them ask follow-up.\n"
                    "- Be direct and substantive. Answer questions, give opinions.\n"
                    "- Match the energy — casual if casual, focused if focused.\n"
                    "- Never say 'How can I help?' — just engage with what was said.\n"
                    "- Never correct your name or re-introduce yourself.\n"
                    "- Have opinions. Don't be wishy-washy."
                ),
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
            return text
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            return None

    async def greet(self):
        """Send a greeting when first joining the meeting."""
        if not self._running:
            return
        self._speaking = True
        try:
            await self.bot.speak(
                "Hi everyone, I'm Gneva! I'll be taking notes. "
                "Feel free to ask me anything."
            )
        finally:
            self._speaking = False
            self._last_spoke_at = time.time()
