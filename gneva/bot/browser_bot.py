"""BrowserBot — single bot instance that joins one meeting via headless Chromium."""

import asyncio
import uuid
import logging
import os
from datetime import datetime, timedelta
from enum import Enum

from gneva.bot.audio_capture import AudioCapture
from gneva.bot.avatar import get_avatar_inject_js, get_speaking_js
from gneva.bot.platforms import detect_platform, get_driver

logger = logging.getLogger(__name__)


class BotState(str, Enum):
    INITIALIZING = "initializing"
    JOINING = "joining"
    IN_LOBBY = "in_lobby"
    IN_MEETING = "in_meeting"
    RECORDING = "recording"
    LEAVING = "leaving"
    ENDED = "ended"
    FAILED = "failed"


class BrowserBot:
    """A single headless browser bot that joins and records one meeting."""

    def __init__(
        self,
        meeting_url: str,
        bot_name: str = "Gneva",
        consent_message: str = "Gneva AI is recording this meeting for notes and action items.",
        audio_dir: str = "/tmp/gneva/audio",
        lobby_timeout: int = 300,
        max_duration: int = 14400,
        meeting_id: str | None = None,
        on_complete=None,
    ):
        self.bot_id = str(uuid.uuid4())
        self.meeting_url = meeting_url
        self.bot_name = bot_name
        self.consent_message = consent_message
        self.audio_dir = audio_dir
        self.lobby_timeout = lobby_timeout
        self.max_duration = max_duration
        self.meeting_id = meeting_id
        self.on_complete = on_complete  # async callback(bot_id, meeting_id, audio_path, success)
        self.on_state_change = None  # async callback(bot_id, meeting_id, new_state)

        self._state = BotState.INITIALIZING
        self.platform = detect_platform(meeting_url)
        self.error: str | None = None
        self.started_at: datetime | None = None
        self.ended_at: datetime | None = None
        self.audio_path: str | None = None

        self._browser = None
        self._context = None
        self._page = None
        self._driver = None
        self._audio_capture: AudioCapture | None = None
        self._stop_event = asyncio.Event()

    @property
    def state(self) -> BotState:
        return self._state

    @state.setter
    def state(self, new_state: BotState):
        old = self._state
        self._state = new_state
        if old != new_state and self.on_state_change and self.meeting_id:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.on_state_change(
                        self.bot_id, self.meeting_id, new_state.value
                    ))
            except Exception:
                pass

    async def run(self, playwright):
        """Main lifecycle: launch browser → join → record → leave."""
        try:
            self.started_at = datetime.utcnow()
            await self._launch_browser(playwright)
            await self._join_meeting()

            if self.state == BotState.FAILED:
                return

            await self._start_recording()
            await self._monitor_meeting()
            await self._leave_meeting()
        except asyncio.CancelledError:
            logger.info(f"Bot {self.bot_id} cancelled")
            self.state = BotState.ENDED
        except Exception as e:
            logger.error(f"Bot {self.bot_id} error: {e}", exc_info=True)
            self.state = BotState.FAILED
            self.error = str(e)
        finally:
            await self._cleanup()

    async def stop(self):
        """Signal the bot to leave and stop."""
        self._stop_event.set()

    async def _launch_browser(self, playwright):
        """Create a browser context with the right flags for meeting audio."""
        self.state = BotState.INITIALIZING

        self._browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--use-fake-ui-for-media-stream",
                "--disable-web-security",
                "--autoplay-policy=no-user-gesture-required",
                "--disable-features=WebRtcHideLocalIpsWithMdns",
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--auto-select-desktop-capture-source=Entire screen",
                "--enable-usermedia-screen-capturing",
            ],
        )

        self._context = await self._browser.new_context(
            permissions=["microphone", "camera", "notifications"],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
        )

        # Override navigator.webdriver to avoid detection
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)

        # Inject avatar system — overrides getUserMedia to serve canvas-based face
        avatar_js = get_avatar_inject_js()
        await self._context.add_init_script(avatar_js)

        self._page = await self._context.new_page()
        self._driver = get_driver(self.platform, self._page, self.bot_name)

        logger.info(f"Bot {self.bot_id}: browser launched for {self.platform}")

    async def _join_meeting(self):
        """Join the meeting using the platform driver."""
        self.state = BotState.JOINING

        success = await self._driver.join(self.meeting_url)
        if not success:
            self.state = BotState.FAILED
            self.error = "Failed to join meeting"
            return

        # Wait in lobby if needed
        lobby_start = datetime.utcnow()
        while await self._driver.is_in_lobby():
            self.state = BotState.IN_LOBBY
            elapsed = (datetime.utcnow() - lobby_start).total_seconds()
            if elapsed > self.lobby_timeout:
                self.state = BotState.FAILED
                self.error = "Lobby timeout — host did not admit the bot"
                return
            if self._stop_event.is_set():
                return
            await asyncio.sleep(5)

        self.state = BotState.IN_MEETING

        # Post consent message
        try:
            await self._driver.post_chat_message(self.consent_message)
        except Exception as e:
            from gneva.config import get_settings
            _settings = get_settings()
            if _settings.bot_consent_required:
                self.state = BotState.FAILED
                self.error = f"Consent message required but failed to post: {e}"
                logger.error(f"Bot {self.bot_id}: consent required but failed: {e}")
                return
            logger.warning(f"Could not post consent message: {e}")

        logger.info(f"Bot {self.bot_id}: in meeting")

    async def _start_recording(self):
        """Inject audio capture JS and start recording."""
        os.makedirs(self.audio_dir, exist_ok=True)
        audio_file = os.path.join(self.audio_dir, f"{self.bot_id}.wav")

        self._audio_capture = AudioCapture(output_path=audio_file)
        await self._audio_capture.start()

        # Inject the audio capture JS via CDP
        js_code = self._audio_capture.get_inject_js()
        cdp = await self._page.context.new_cdp_session(self._page)
        await cdp.send("Runtime.evaluate", {"expression": js_code})

        self.state = BotState.RECORDING
        logger.info(f"Bot {self.bot_id}: recording started, audio WS on port {self._audio_capture.port}")

    async def _monitor_meeting(self):
        """Poll for meeting end, stop signal, or max duration.

        Fallbacks beyond CSS selectors:
        - No audio for 60+ seconds while recording -> meeting likely ended
        - Page URL changed (redirected away) -> meeting ended
        - Periodic state logging for debugging
        """
        deadline = datetime.utcnow() + timedelta(seconds=self.max_duration)
        initial_url = self._page.url if self._page else ""
        last_audio_bytes = self._audio_capture._total_bytes if self._audio_capture else 0
        last_audio_change = datetime.utcnow()
        last_log_time = datetime.utcnow()
        silence_threshold_sec = 60  # seconds of silence before assuming meeting ended
        poll_count = 0

        while not self._stop_event.is_set():
            poll_count += 1

            # Check if meeting ended via platform driver selectors
            try:
                if await self._driver.detect_meeting_ended():
                    logger.info(f"Bot {self.bot_id}: meeting ended (detected by driver)")
                    break
            except Exception as e:
                logger.warning(f"Bot {self.bot_id}: detect_meeting_ended error: {e}")

            # Fallback: check if page URL has changed (redirected away from meeting)
            try:
                current_url = self._page.url if self._page else ""
                if initial_url and current_url and current_url != initial_url:
                    # URL changed — check if it looks like we left the meeting
                    if not any(
                        domain in current_url.lower()
                        for domain in [
                            "teams.microsoft.com", "teams.live.com",
                            "zoom.us", "zoom.com",
                            "meet.google.com",
                        ]
                    ):
                        logger.info(
                            f"Bot {self.bot_id}: meeting ended — URL changed "
                            f"from {initial_url} to {current_url}"
                        )
                        break
            except Exception:
                pass

            # Fallback: detect audio silence timeout
            if self._audio_capture and self.state == BotState.RECORDING:
                current_bytes = self._audio_capture._total_bytes
                if current_bytes > last_audio_bytes:
                    last_audio_bytes = current_bytes
                    last_audio_change = datetime.utcnow()
                else:
                    silence_sec = (datetime.utcnow() - last_audio_change).total_seconds()
                    if silence_sec >= silence_threshold_sec:
                        logger.info(
                            f"Bot {self.bot_id}: no audio for {silence_sec:.0f}s — "
                            f"assuming meeting ended (silence timeout)"
                        )
                        break

            # Check max duration
            if datetime.utcnow() > deadline:
                logger.info(f"Bot {self.bot_id}: max duration reached")
                break

            # Periodic debug logging (every ~60 seconds = 12 polls at 5s interval)
            now = datetime.utcnow()
            if (now - last_log_time).total_seconds() >= 60:
                audio_info = ""
                if self._audio_capture:
                    audio_info = (
                        f", audio={self._audio_capture.duration_sec:.1f}s "
                        f"({self._audio_capture._total_bytes / 1024:.0f} KB)"
                    )
                elapsed = (now - self.started_at).total_seconds() if self.started_at else 0
                logger.info(
                    f"Bot {self.bot_id}: monitoring — state={self.state.value}, "
                    f"elapsed={elapsed:.0f}s, polls={poll_count}{audio_info}"
                )
                last_log_time = now

            await asyncio.sleep(5)

    async def _leave_meeting(self):
        """Leave the meeting and finalize audio."""
        self.state = BotState.LEAVING

        try:
            await self._driver.leave()
        except Exception as e:
            logger.warning(f"Bot {self.bot_id}: leave error: {e}")

        # Save audio
        if self._audio_capture:
            self.audio_path = await self._audio_capture.stop()
            logger.info(
                f"Bot {self.bot_id}: audio saved "
                f"({self._audio_capture.duration_sec:.1f}s)"
            )

            # If no audio was captured, save diagnostic info
            if not self._audio_capture.has_audio:
                await self._save_diagnostics()

        self.ended_at = datetime.utcnow()
        self.state = BotState.ENDED

        # Trigger pipeline callback
        if self.on_complete:
            try:
                await self.on_complete(
                    bot_id=self.bot_id,
                    meeting_id=self.meeting_id,
                    audio_path=self.audio_path,
                    success=self._audio_capture.has_audio if self._audio_capture else False,
                )
            except Exception as e:
                logger.error(f"Bot {self.bot_id}: on_complete callback error: {e}")

    async def _save_diagnostics(self):
        """Save screenshot and page content when no audio was captured, for debugging."""
        diag_dir = os.path.join(self.audio_dir, "diagnostics")
        os.makedirs(diag_dir, exist_ok=True)
        prefix = os.path.join(diag_dir, self.bot_id)

        try:
            if self._page:
                # Screenshot
                screenshot_path = f"{prefix}_screenshot.png"
                await self._page.screenshot(path=screenshot_path, full_page=True)
                logger.info(f"Bot {self.bot_id}: diagnostic screenshot saved to {screenshot_path}")

                # Page content
                content_path = f"{prefix}_page.html"
                content = await self._page.content()
                with open(content_path, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.info(f"Bot {self.bot_id}: diagnostic page content saved to {content_path}")

                # Console log from the page
                url = self._page.url
                logger.warning(
                    f"Bot {self.bot_id}: NO AUDIO captured. "
                    f"Current URL: {url}. "
                    f"Diagnostics saved to {diag_dir}. "
                    f"Audio capture via WebSocket may have failed — "
                    f"check if WebRTC tracks were intercepted."
                )
        except Exception as e:
            logger.warning(f"Bot {self.bot_id}: failed to save diagnostics: {e}")

    async def _cleanup(self):
        """Close browser and free resources."""
        try:
            if self._audio_capture and self._audio_capture._running:
                await self._audio_capture.stop()
        except Exception:
            pass

        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass

        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass

        logger.info(f"Bot {self.bot_id}: cleaned up")

    async def speak(self, text: str):
        """Synthesize speech via TTS and play it into the meeting.

        This triggers the avatar lip-sync animation and injects
        audio into the meeting via a MediaStream audio source.
        """
        if not self._page or self.state not in (BotState.IN_MEETING, BotState.RECORDING):
            logger.warning(f"Bot {self.bot_id}: cannot speak — not in meeting")
            return

        try:
            from gneva.services.tts import TTSService
            tts = TTSService()
            audio_bytes = await tts.synthesize(text)

            # Convert WAV to base64 for browser injection
            import base64
            audio_b64 = base64.b64encode(audio_bytes).decode()

            # Start lip-sync animation
            cdp = await self._page.context.new_cdp_session(self._page)
            await cdp.send("Runtime.evaluate", {
                "expression": get_speaking_js(True)
            })

            # Inject and play audio in the browser (feeds into the meeting audio)
            play_js = f"""
            (async () => {{
                try {{
                    const b64 = '{audio_b64}';
                    const binary = atob(b64);
                    const bytes = new Uint8Array(binary.length);
                    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
                    const audioCtx = new AudioContext({{ sampleRate: 22050 }});
                    const buffer = await audioCtx.decodeAudioData(bytes.buffer);
                    const source = audioCtx.createBufferSource();
                    source.buffer = buffer;

                    // Create a MediaStreamDestination to feed into getUserMedia
                    const dest = audioCtx.createMediaStreamDestination();
                    source.connect(dest);
                    source.connect(audioCtx.destination);  // also play locally for debugging
                    source.start();

                    // Return duration so we know when to stop lip-sync
                    window.__gnevaLastSpeechDuration = buffer.duration;
                }} catch(e) {{
                    console.error('[Gneva] Speech playback error:', e);
                }}
            }})();
            """
            await cdp.send("Runtime.evaluate", {"expression": play_js})

            # Wait for speech to finish, then stop lip-sync
            # Get the duration from the browser
            dur_result = await cdp.send("Runtime.evaluate", {
                "expression": "window.__gnevaLastSpeechDuration || 3",
                "returnByValue": True,
            })
            duration = dur_result.get("result", {}).get("value", 3)
            await asyncio.sleep(duration + 0.3)

            await cdp.send("Runtime.evaluate", {
                "expression": get_speaking_js(False)
            })
            logger.info(f"Bot {self.bot_id}: spoke for {duration:.1f}s — '{text[:50]}...'")
        except Exception as e:
            logger.error(f"Bot {self.bot_id}: speak error: {e}", exc_info=True)
            # Make sure lip-sync stops even on error
            try:
                cdp = await self._page.context.new_cdp_session(self._page)
                await cdp.send("Runtime.evaluate", {
                    "expression": get_speaking_js(False)
                })
            except Exception:
                pass

    def to_dict(self) -> dict:
        """Return bot status as a dict."""
        return {
            "bot_id": self.bot_id,
            "meeting_id": self.meeting_id,
            "state": self.state.value,
            "platform": self.platform,
            "bot_name": self.bot_name,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "audio_path": self.audio_path,
            "duration_sec": (
                self._audio_capture.duration_sec if self._audio_capture else 0
            ),
        }
