"""BotManager — manages bot lifecycle, tracks active bots, runs as background tasks."""

import asyncio
import logging
from datetime import datetime
from typing import Union

from gneva.bot.browser_bot import BrowserBot, BotState

logger = logging.getLogger(__name__)


def _should_use_acs() -> bool:
    """Check if ACS Calling SDK should be used instead of browser caption scraping."""
    try:
        from gneva.config import get_settings
        settings = get_settings()
        # ACS Calling SDK needs a connection string for identity/token generation
        return bool(settings.acs_connection_string)
    except Exception:
        return False


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

        self._bots: dict[str, Union[BrowserBot, "ACSBot"]] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._playwright = None
        self._started = False
        self._use_acs = _should_use_acs()

    async def start(self):
        """Initialize Playwright (needed for both browser bot and ACS Calling SDK)."""
        if self._started:
            return

        from playwright.async_api import async_playwright
        self._pw_context = async_playwright()
        self._playwright = await self._pw_context.start()
        self._started = True

        if self._use_acs:
            logger.info("BotManager started — using ACS Calling SDK (real audio, Playwright for SDK runtime)")
        else:
            logger.info("BotManager started — using browser caption scraping (Playwright)")

    async def stop(self):
        """Stop all bots and cleanup Playwright."""
        # Signal all active bots to stop
        for bot_id, bot in list(self._bots.items()):
            try:
                await bot.stop()
            except Exception as e:
                logger.warning(f"Error signaling bot {bot_id} to stop: {e}")

        # Wait for all bot tasks to finish with a timeout
        tasks = [t for t in self._tasks.values() if not t.done()]
        if tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=10,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    f"Timed out waiting for {len(tasks)} bot(s) to stop — cancelling"
                )
                for task in tasks:
                    task.cancel()
                # Give cancelled tasks a moment to clean up
                await asyncio.gather(*tasks, return_exceptions=True)

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
        org_id: str | None = None,
        greeting_mode: str = "personalized",
    ) -> str:
        """
        Launch a bot to join a meeting. Returns the bot_id.

        Args:
            meeting_url: The meeting URL (Zoom, Meet, or Teams)
            meeting_id: Database meeting ID to associate
            bot_name: Override the default bot name
            on_complete: async callback(bot_id, meeting_id, audio_path, success)
            voice_id: ElevenLabs voice ID for TTS
            org_id: Organization ID for cross-meeting memory
            greeting_mode: Greeting style (personalized, professional, casual, silent, etc.)
        """
        if not self._started:
            await self.start()

        active = sum(1 for b in self._bots.values() if b.state in (
            BotState.JOINING, BotState.IN_LOBBY, BotState.IN_MEETING, BotState.RECORDING
        ))
        if active >= self.max_concurrent:
            raise RuntimeError(f"Max concurrent bots ({self.max_concurrent}) reached")

        bot_kwargs = dict(
            meeting_url=meeting_url,
            bot_name=bot_name or self.bot_name,
            consent_message=self.consent_message,
            audio_dir=self.audio_dir,
            lobby_timeout=self.lobby_timeout,
            max_duration=self.max_duration,
            meeting_id=meeting_id,
            on_complete=on_complete,
            voice_id=voice_id,
            org_id=org_id,
            greeting_mode=greeting_mode,
        )

        if self._use_acs:
            from gneva.bot.acs_calling_bot import ACSCallingBot
            bot = ACSCallingBot(**bot_kwargs)
            logger.info(f"Using ACSCallingBot (real audio) for {meeting_url}")
        else:
            bot = BrowserBot(**bot_kwargs)
            logger.info(f"Using BrowserBot (caption scraping) for {meeting_url}")

        bot.on_state_change = self._on_bot_state_change

        self._bots[bot.bot_id] = bot
        task = asyncio.create_task(self._run_bot(bot))
        self._tasks[bot.bot_id] = task

        logger.info(f"Bot {bot.bot_id} launched for {meeting_url}")
        return bot.bot_id

    async def join_visual_only(
        self,
        meeting_url: str,
        meeting_id: str | None = None,
        org_id: str | None = None,
    ) -> str:
        """Launch a visual-only browser bot (no audio/TTS — just captions + screen capture).

        Used alongside Twilio phone dial-in: phone handles voice, browser handles eyes.
        """
        if not self._started:
            await self.start()

        bot = BrowserBot(
            meeting_url=meeting_url,
            bot_name="Raj",
            consent_message="",
            audio_dir=self.audio_dir,
            lobby_timeout=self.lobby_timeout,
            max_duration=self.max_duration,
            meeting_id=meeting_id,
            on_complete=None,  # No pipeline trigger — phone side handles that
            org_id=org_id,
            greeting_mode="silent",
            visual_only=True,
        )
        bot.on_state_change = self._on_bot_state_change

        self._bots[bot.bot_id] = bot
        task = asyncio.create_task(self._run_bot(bot))
        self._tasks[bot.bot_id] = task

        logger.info(f"Visual-only bot {bot.bot_id} launched for {meeting_url}")
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

    async def _run_bot(self, bot):
        """Run a bot as a background task."""
        try:
            await bot.run(self._playwright)  # ACSBot ignores the playwright arg
        except Exception as e:
            logger.error(f"Bot {bot.bot_id} task error: {e}", exc_info=True)
        finally:
            # Clean up completed bot after a while (keep status available for 10 min)
            await asyncio.sleep(600)
            self._bots.pop(bot.bot_id, None)
            self._tasks.pop(bot.bot_id, None)
