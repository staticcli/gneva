"""Zoom web client driver."""

import asyncio
import re
from gneva.bot.platforms.base import BasePlatformDriver


# Zoom Web Client selectors — multiple fallbacks for UI version changes
S = {
    # Pre-join / preview screen
    "name_input": "#inputname, input[placeholder*='name' i], input[aria-label*='name' i]",
    "join_button": "button.preview-join-button, button#joinBtn, button:has-text('Join')",
    "passcode_input": "#inputpasscode, input[placeholder*='passcode' i], input[type='password']",
    "passcode_submit": "button.submit-btn, button:has-text('Submit'), button:has-text('Join Meeting')",

    # Audio join
    "join_audio": "button:has-text('Join Audio by Computer'), button:has-text('Join Audio'), button[class*='join-audio']",
    "join_audio_alt": "button:has-text('Join with Computer Audio')",

    # Mute / camera
    "mute_btn": "button[aria-label*='mute' i]:not([aria-label*='unmute' i]), button[aria-label*='Mute' i]:not([aria-label*='Unmute' i])",
    "unmuted_indicator": "button[aria-label*='Mute' i]:not([aria-label*='Unmute' i])",
    "camera_off_btn": "button[aria-label*='stop' i][aria-label*='video' i], button[aria-label*='Stop Video' i]",
    "camera_on_indicator": "button[aria-label*='Stop Video' i], button[aria-label*='stop video' i]",

    # Camera off on preview
    "preview_camera_off": "button[aria-label*='stop' i][aria-label*='video' i]",
    "preview_mute": "button[aria-label*='mute' i]",

    # Chat
    "chat_button": "button[aria-label*='chat' i], button[aria-label*='Chat' i]",
    "chat_input": "textarea.chat-box__chat-textarea, div[class*='chat-input'] textarea, textarea[placeholder*='message' i]",
    "chat_send": "button[class*='chat-send'], button[aria-label*='send' i]",

    # Meeting ended
    "meeting_ended": (
        "[class*='meeting-ended'], [class*='MeetingEndedCard'], "
        "h2:has-text('This meeting has been ended'), "
        "div:has-text('This meeting has been ended by host'), "
        "div:has-text('The host has ended this meeting'), "
        "h2:has-text('This meeting has ended')"
    ),
    "removed": "div:has-text('host has removed you'), div:has-text('been removed')",
    "rejoin_button": (
        "button:has-text('Rejoin'), button:has-text('rejoin'), "
        "a:has-text('Rejoin'), button:has-text('Rejoin Meeting')"
    ),

    # Consent dialog / cookie popup
    "cookie_accept": "button:has-text('Accept'), button:has-text('Got it'), button#onetrust-accept-btn-handler",

    # Web client link (when Zoom tries to open desktop app)
    "web_client_link": "a:has-text('Join from Your Browser'), a:has-text('join from your browser'), a[href*='wc/join']",
    "launch_meeting_btn": "button:has-text('Launch Meeting'), button#launch-meeting",
}


class ZoomDriver(BasePlatformDriver):
    """Zoom Web Client meeting automation."""

    async def join(self, meeting_url: str) -> bool:
        self.logger.info(f"Joining Zoom meeting: {meeting_url}")

        # Convert native zoom links to web client links
        web_url = self._to_web_client_url(meeting_url)
        await self.page.goto(web_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)

        # Handle "open in desktop app" prompt — click "Join from browser" instead
        await self._click_if_visible(S["cookie_accept"])
        if await self._click_if_visible(S["web_client_link"], timeout=5000):
            self.logger.info("Clicked 'Join from browser'")
            await asyncio.sleep(3)

        # Enter bot name
        if await self._fill_if_visible(S["name_input"], self.bot_name, timeout=5000):
            self.logger.info(f"Entered name: {self.bot_name}")

        # Mute + camera off on preview screen
        await self._click_if_visible(S["preview_mute"], timeout=2000)
        await self._click_if_visible(S["preview_camera_off"], timeout=2000)

        # Click join
        if not await self._click_if_visible(S["join_button"], timeout=5000):
            self.logger.error("Could not find join button")
            return False

        self.logger.info("Clicked join")
        await asyncio.sleep(3)

        # Handle passcode if prompted
        passcode_visible = await self._is_visible(S["passcode_input"], timeout=3000)
        if passcode_visible:
            self.logger.warning("Meeting requires passcode — cannot join without it")
            return False

        # Join audio
        for attempt in range(3):
            if await self._click_if_visible(S["join_audio"], timeout=5000):
                self.logger.info("Joined audio by computer")
                break
            if await self._click_if_visible(S["join_audio_alt"], timeout=2000):
                self.logger.info("Joined with computer audio (alt)")
                break
            await asyncio.sleep(2)

        await asyncio.sleep(2)
        await self.ensure_muted()
        await self.ensure_camera_off()

        self.logger.info("Successfully joined Zoom meeting")
        return True

    async def ensure_muted(self):
        # If the unmuted indicator is visible, we need to click it to mute
        if await self._is_visible(S["unmuted_indicator"], timeout=1000):
            await self._click_if_visible(S["mute_btn"])
            self.logger.info("Muted microphone")

    async def ensure_camera_off(self):
        if await self._is_visible(S["camera_on_indicator"], timeout=1000):
            await self._click_if_visible(S["camera_off_btn"])
            self.logger.info("Turned off camera")

    async def post_chat_message(self, message: str):
        # Open chat panel
        await self._click_if_visible(S["chat_button"], timeout=3000)
        await asyncio.sleep(1)

        # Type and send
        if await self._fill_if_visible(S["chat_input"], message, timeout=3000):
            # Try send button, fall back to Enter key
            if not await self._click_if_visible(S["chat_send"], timeout=1000):
                chat_box = self.page.locator(S["chat_input"]).first
                await chat_box.press("Enter")
            self.logger.info("Posted chat message")
        else:
            self.logger.warning("Could not find chat input")

    async def detect_meeting_ended(self) -> bool:
        # Check explicit "meeting ended" text indicators
        if await self._is_visible(S["meeting_ended"], timeout=500):
            self.logger.info("Meeting ended: detected end text")
            return True

        if await self._is_visible(S["removed"], timeout=300):
            self.logger.info("Meeting ended: detected removal text")
            return True

        # Check for "Rejoin" button — appears after meeting ends
        if await self._is_visible(S["rejoin_button"], timeout=300):
            self.logger.info("Meeting ended: detected Rejoin button")
            return True

        # Check if page navigated away from the meeting
        current_url = self.page.url
        if current_url and not any(
            x in current_url.lower()
            for x in ["zoom.us", "zoom.com"]
        ):
            self.logger.info(f"Meeting ended: page navigated away to {current_url}")
            return True

        return False

    async def is_in_lobby(self) -> bool:
        # Zoom shows a "Please wait, the meeting host will let you in soon" message
        return await self._is_visible(
            "div:has-text('waiting for the host'), div:has-text('Please wait')",
            timeout=500,
        )

    async def leave(self):
        try:
            leave_btn = self.page.locator(
                "button[aria-label*='leave' i], button:has-text('Leave'), button:has-text('End')"
            ).first
            await leave_btn.click(timeout=3000)
            await asyncio.sleep(1)
            # Confirm leave dialog
            await self._click_if_visible("button:has-text('Leave Meeting')", timeout=2000)
        except Exception as e:
            self.logger.warning(f"Could not click leave button: {e}")

    def _to_web_client_url(self, url: str) -> str:
        """Convert zoom.us/j/123456 to web client URL."""
        # Already a web client URL
        if "/wc/" in url or "/wc/join/" in url:
            return url

        # Extract meeting ID from various URL formats
        match = re.search(r"zoom\.us/j/(\d+)", url)
        if match:
            meeting_id = match.group(1)
            # Preserve query params (password, etc.)
            query = ""
            if "?" in url:
                query = "?" + url.split("?", 1)[1]
            return f"https://app.zoom.us/wc/join/{meeting_id}{query}"

        return url
