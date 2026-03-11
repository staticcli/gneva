"""Microsoft Teams web client driver — supports both classic and light-meetings."""

import asyncio
from gneva.bot.platforms.base import BasePlatformDriver


S = {
    # Landing page — "Continue on this browser" vs "Open Teams app"
    "continue_browser": "button:has-text('Continue on this browser'), a:has-text('Continue on this browser'), button:has-text('Join on the web instead')",

    # Guest join — both classic and light-meetings selectors
    "name_input": "input[placeholder='Type your name'], input[placeholder*='name' i], input[aria-label*='name' i], input#username",
    "join_button": "button:has-text('Join now'), button[data-tid='prejoin-join-button']",

    # Pre-join toggles
    "mic_toggle": "button[aria-label*='Mic' i], div[role='checkbox'][aria-label*='Mic' i], toggle-button[aria-label*='Mic' i]",
    "cam_toggle": "button[aria-label*='Camera' i], div[role='checkbox'][aria-label*='Camera' i], toggle-button[aria-label*='Camera' i]",

    # In-meeting controls
    "mic_button": "button[aria-label*='Mute' i], button[id*='microphone' i], button[aria-label*='Mic' i]",
    "cam_button": "button[aria-label*='video' i], button[id*='video' i], button[aria-label*='Camera' i]",
    "mic_on_indicator": "button[aria-label*='Mute' i]:not([aria-label*='Unmute' i])",
    "cam_on_indicator": "button[aria-label*='Turn camera off' i]",

    # Chat
    "chat_button": "button[aria-label*='Chat' i], button[id*='chat' i]",
    "chat_input": "div[role='textbox'][aria-label*='message' i], div[contenteditable='true'], textarea[placeholder*='message' i]",
    "chat_send": "button[aria-label*='Send' i]",

    # Meeting state — both classic and light
    "lobby": (
        "div:has-text('Someone in the meeting should let you in soon'), "
        "div:has-text('waiting in the lobby'), "
        "div:has-text('Someone will let you in shortly')"
    ),
    "meeting_ended": (
        "div:has-text('meeting has ended'), div:has-text('You left the meeting'), "
        "div:has-text('removed from this meeting'), div:has-text('The meeting has ended'), "
        "div:has-text('Meeting has ended'), div:has-text('You have been removed')"
    ),
    "rejoin_button": (
        "button:has-text('Rejoin'), button:has-text('rejoin'), "
        "button:has-text('Rejoin meeting'), a:has-text('Rejoin')"
    ),
    "participant_count": (
        "span[data-tid='participant-count'], button[aria-label*='participant' i] span, "
        "span[class*='participants-count'], [data-cid='roster-button'] span"
    ),

    # Popups / dialogs
    "dismiss": "button:has-text('OK'), button:has-text('Got it'), button:has-text('Continue')",
    "cookie_accept": "button:has-text('Accept'), button#accept-cookies",
    "media_dialog_cancel": "button:has-text('Cancel')",
    "continue_without_media": "button:has-text('Continue without audio or video')",
}


class TeamsDriver(BasePlatformDriver):
    """Microsoft Teams Web client meeting automation — classic + light-meetings."""

    async def join(self, meeting_url: str) -> bool:
        self.logger.info(f"Joining Teams meeting: {meeting_url}")

        await self.page.goto(meeting_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Accept cookies
        await self._click_if_visible(S["cookie_accept"])
        await asyncio.sleep(1)

        # Click "Continue on this browser" to use web client
        if await self._click_if_visible(S["continue_browser"], timeout=8000):
            self.logger.info("Selected web browser client")
        else:
            self.logger.warning("Could not find 'Continue on browser' — trying to proceed")

        # Light-meetings takes longer to load (~15-20s)
        self.logger.info("Waiting for pre-join screen to load...")
        await asyncio.sleep(15)

        # Handle "Are you sure you don't want audio/video?" dialog
        try:
            if await self._is_visible(S["continue_without_media"], timeout=3000):
                self.logger.info("Media permission dialog appeared")
                # Try cancel first (we want media)
                if not await self._click_if_visible(S["media_dialog_cancel"], timeout=1000):
                    # If no cancel, continue without — avatar JS still works
                    await self._click_if_visible(S["continue_without_media"])
                await asyncio.sleep(3)
        except Exception:
            pass

        # Dismiss any popups
        await self._click_if_visible(S["dismiss"])

        # Enter bot name
        if await self._fill_if_visible(S["name_input"], self.bot_name, timeout=5000):
            self.logger.info(f"Entered name: {self.bot_name}")
        else:
            self.logger.warning("Could not find name input")

        await asyncio.sleep(1)

        # Click "Join now"
        if not await self._click_if_visible(S["join_button"], timeout=5000):
            self.logger.error("Could not find join button")
            return False

        self.logger.info("Clicked join — may be in lobby")
        await asyncio.sleep(5)

        # Ensure mic muted (keep camera ON for avatar)
        await self.ensure_muted()

        self.logger.info("Successfully joined Teams meeting")
        return True

    async def ensure_muted(self):
        if await self._is_visible(S["mic_on_indicator"], timeout=1000):
            await self._click_if_visible(S["mic_button"])
            self.logger.info("Muted microphone")

    async def ensure_camera_off(self):
        if await self._is_visible(S["cam_on_indicator"], timeout=1000):
            await self._click_if_visible(S["cam_button"])
            self.logger.info("Turned off camera")

    async def post_chat_message(self, message: str):
        await self._click_if_visible(S["chat_button"], timeout=3000)
        await asyncio.sleep(1)

        chat = self.page.locator(S["chat_input"]).first
        try:
            await chat.wait_for(state="visible", timeout=3000)
            await chat.fill(message)
            await asyncio.sleep(0.5)
            if not await self._click_if_visible(S["chat_send"], timeout=1000):
                await chat.press("Enter")
            self.logger.info("Posted chat message")
        except Exception as e:
            self.logger.warning(f"Could not post chat message: {e}")

    async def detect_meeting_ended(self) -> bool:
        if await self._is_visible(S["meeting_ended"], timeout=500):
            self.logger.info("Meeting ended: detected end text")
            return True

        if await self._is_visible(S["rejoin_button"], timeout=300):
            self.logger.info("Meeting ended: detected Rejoin button")
            return True

        current_url = self.page.url
        if current_url and not any(
            x in current_url.lower()
            for x in ["teams.microsoft.com", "teams.live.com", "teams.cloud.microsoft"]
        ):
            self.logger.info(f"Meeting ended: page navigated away to {current_url}")
            return True

        try:
            loc = self.page.locator(S["participant_count"]).first
            text = await loc.text_content(timeout=300)
            if text:
                count = int("".join(c for c in text if c.isdigit()) or "0")
                if count <= 1:
                    self.logger.info(f"Meeting ended: only {count} participant(s) remaining")
                    return True
        except Exception:
            pass

        return False

    async def is_in_lobby(self) -> bool:
        return await self._is_visible(S["lobby"], timeout=500)

    async def leave(self):
        try:
            leave = self.page.locator(
                "button[aria-label*='Leave' i], button:has-text('Leave'), button[id*='hangup' i]"
            ).first
            await leave.click(timeout=3000)
        except Exception as e:
            self.logger.warning(f"Could not click leave: {e}")
