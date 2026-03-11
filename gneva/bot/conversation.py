"""Real-time conversation engine — listens to meeting audio, responds via TTS.

Flow: Audio capture → Speech-to-text → AI response → TTS → Lip-sync playback
"""

import asyncio
import logging
import json

logger = logging.getLogger(__name__)


class ConversationEngine:
    """Manages real-time conversation for a bot in a meeting."""

    def __init__(self, bot, org_id: str | None = None):
        self.bot = bot
        self.org_id = org_id
        self._running = False
        self._transcript_buffer: list[dict] = []
        self._last_response_text = ""
        self._cooldown_sec = 5  # minimum seconds between responses
        self._last_spoke_at = 0

    async def start(self):
        """Start listening for conversation triggers."""
        self._running = True
        logger.info(f"Conversation engine started for bot {self.bot.bot_id}")

    async def stop(self):
        """Stop the conversation engine."""
        self._running = False
        logger.info(f"Conversation engine stopped for bot {self.bot.bot_id}")

    async def on_transcript_segment(self, text: str, speaker: str):
        """Called when a new transcript segment is received.

        This is fed by the real-time transcription of meeting audio.
        """
        if not self._running:
            return

        self._transcript_buffer.append({"speaker": speaker, "text": text})

        # Keep last 20 segments for context
        if len(self._transcript_buffer) > 20:
            self._transcript_buffer = self._transcript_buffer[-20:]

        # Check if someone is addressing Gneva
        text_lower = text.lower()
        addressed = any(trigger in text_lower for trigger in [
            "gneva", "geneva", "hey gneva", "gneva,",
            "what do you think", "can you", "gneva?",
        ])

        if addressed:
            import time
            now = time.time()
            if now - self._last_spoke_at < self._cooldown_sec:
                return

            self._last_spoke_at = now
            response = await self._generate_response(text, speaker)
            if response:
                await self.bot.speak(response)

    async def _generate_response(self, trigger_text: str, speaker: str) -> str | None:
        """Generate an AI response to the conversation."""
        try:
            from gneva.services import get_anthropic_client
            client = get_anthropic_client()

            # Build conversation context
            context_lines = []
            for seg in self._transcript_buffer[-10:]:
                context_lines.append(f"{seg['speaker']}: {seg['text']}")
            context = "\n".join(context_lines)

            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
                system=(
                    "You are Gneva, an AI team member in a live meeting. "
                    "You are helpful, concise, and professional. "
                    "Keep responses brief (1-2 sentences) since you're speaking aloud. "
                    "Be natural and conversational, not robotic."
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Meeting context:\n{context}\n\n"
                        f"{speaker} just said: \"{trigger_text}\"\n\n"
                        f"Respond naturally as Gneva."
                    ),
                }],
            )

            text = response.content[0].text.strip()
            logger.info(f"Gneva response: {text[:80]}...")
            return text
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            return None

    async def greet(self):
        """Send a greeting when first joining the meeting."""
        if not self._running:
            return
        await self.bot.speak(
            "Hi everyone! I'm Gneva, your AI team member. "
            "I'll be taking notes and tracking action items. "
            "Feel free to ask me anything during the meeting."
        )
