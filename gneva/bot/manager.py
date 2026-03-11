"""BotManager — manages bot lifecycle, tracks active bots, runs as background tasks."""

import asyncio
import logging
from datetime import datetime

from gneva.bot.browser_bot import BrowserBot, BotState

logger = logging.getLogger(__name__)


class BotManager:
    """Singleton that manages all active meeting bots."""

    def __init__(
        self,
        bot_name: str = "Gneva",
        consent_message: str = "Gneva AI is recording this meeting for notes and action items.",
        audio_dir: str = "/tmp/gneva/audio",
        max_concurrent: int = 5,
        lobby_timeout: int = 300,
        max_duration: int = 14400,
    ):
        self.bot_name = bot_name
        self.consent_message = consent_message
        self.audio_dir = audio_dir
        self.max_concurrent = max_concurrent
        self.lobby_timeout = lobby_timeout
        self.max_duration = max_duration

        self._bots: dict[str, BrowserBot] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._playwright = None
        self._started = False

    async def start(self):
        """Initialize Playwright."""
        if self._started:
            return

        from playwright.async_api import async_playwright
        self._pw_context = async_playwright()
        self._playwright = await self._pw_context.start()
        self._started = True
        logger.info("BotManager started — Playwright initialized")

    async def stop(self):
        """Stop all bots and cleanup Playwright."""
        for bot_id in list(self._bots.keys()):
            await self.leave(bot_id)

        # Cancel remaining tasks
        for task in self._tasks.values():
            task.cancel()

        if self._playwright:
            await self._playwright.stop()
            self._started = False

        logger.info("BotManager stopped")

    async def join(
        self,
        meeting_url: str,
        meeting_id: str | None = None,
        bot_name: str | None = None,
        on_complete=None,
        voice_id: str | None = None,
    ) -> str:
        """
        Launch a bot to join a meeting. Returns the bot_id.

        Args:
            meeting_url: The meeting URL (Zoom, Meet, or Teams)
            meeting_id: Database meeting ID to associate
            bot_name: Override the default bot name
            on_complete: async callback(bot_id, meeting_id, audio_path, success)
            voice_id: ElevenLabs voice ID for TTS
        """
        if not self._started:
            await self.start()

        active = sum(1 for b in self._bots.values() if b.state in (
            BotState.JOINING, BotState.IN_LOBBY, BotState.IN_MEETING, BotState.RECORDING
        ))
        if active >= self.max_concurrent:
            raise RuntimeError(f"Max concurrent bots ({self.max_concurrent}) reached")

        bot = BrowserBot(
            meeting_url=meeting_url,
            bot_name=bot_name or self.bot_name,
            consent_message=self.consent_message,
            audio_dir=self.audio_dir,
            lobby_timeout=self.lobby_timeout,
            max_duration=self.max_duration,
            meeting_id=meeting_id,
            on_complete=on_complete,
            voice_id=voice_id,
        )
        bot.on_state_change = self._on_bot_state_change

        self._bots[bot.bot_id] = bot
        task = asyncio.create_task(self._run_bot(bot))
        self._tasks[bot.bot_id] = task

        logger.info(f"Bot {bot.bot_id} launched for {meeting_url}")
        return bot.bot_id

    async def leave(self, bot_id: str):
        """Signal a bot to leave its meeting."""
        bot = self._bots.get(bot_id)
        if not bot:
            raise KeyError(f"Bot {bot_id} not found")

        await bot.stop()
        logger.info(f"Bot {bot_id} signaled to leave")

    def status(self, bot_id: str) -> dict:
        """Get the status of a bot."""
        bot = self._bots.get(bot_id)
        if not bot:
            raise KeyError(f"Bot {bot_id} not found")
        return bot.to_dict()

    def list_bots(self) -> list[dict]:
        """List all bots (active and recent)."""
        return [bot.to_dict() for bot in self._bots.values()]

    @staticmethod
    async def _on_bot_state_change(bot_id: str, meeting_id: str, new_state: str):
        """Update the meeting record when bot state changes."""
        try:
            from gneva.db import async_session_factory
            from gneva.models.meeting import Meeting
            from sqlalchemy import select
            import uuid

            # Map bot states to meeting statuses
            state_map = {
                "joining": "joining",
                "in_lobby": "joining",
                "in_meeting": "active",
                "recording": "active",
                "leaving": "processing",
                "ended": "processing",
                "failed": "failed",
            }
            meeting_status = state_map.get(new_state, "joining")

            async with async_session_factory() as session:
                result = await session.execute(
                    select(Meeting).where(Meeting.id == uuid.UUID(meeting_id))
                )
                meeting = result.scalar_one_or_none()
                if meeting:
                    meeting.status = meeting_status
                    await session.commit()
                    logger.info(f"Meeting {meeting_id} status -> {meeting_status} (bot: {new_state})")
        except Exception as e:
            logger.warning(f"Failed to update meeting status: {e}")

    async def _run_bot(self, bot: BrowserBot):
        """Run a bot as a background task."""
        try:
            await bot.run(self._playwright)
        except Exception as e:
            logger.error(f"Bot {bot.bot_id} task error: {e}", exc_info=True)
        finally:
            # Clean up completed bot after a while (keep status available for 10 min)
            await asyncio.sleep(600)
            self._bots.pop(bot.bot_id, None)
            self._tasks.pop(bot.bot_id, None)
