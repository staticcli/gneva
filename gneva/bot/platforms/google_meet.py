"""Google Meet driver."""

import asyncio
from gneva.bot.platforms.base import BasePlatformDriver


S = {
    # Pre-join screen
    "name_input": "input[aria-label*='name' i], input[placeholder*='name' i], input[data-placeholder*='name' i]",
    "ask_to_join": "button:has-text('Ask to join'), button:has-text('Join now'), button[data-mdc-dialog-action='join']",

    # Guest entry  — "Your name" input on the guest join screen
    "guest_name": "input[type='text'][aria-label*='name' i]",

    # Pre-join toggles (mic/cam) — these are on the preview screen
    "mic_toggle": "div[role='button'][aria-label*='microphone' i], div[role='button'][data-is-muted]",
    "cam_toggle": "div[role='button'][aria-label*='camera' i], div[role='button'][data-is-off]",

    # In-meeting controls
    "mic_button": "button[aria-label*='microphone' i], button[data-tooltip*='microphone' i]",
    "cam_button": "button[aria-label*='camera' i], button[data-tooltip*='camera' i]",
    "mic_muted_check": "[aria-label*='Turn on microphone' i], [data-tooltip*='Turn on microphone' i]",
    "cam_off_check": "[aria-label*='Turn on camera' i], [data-tooltip*='Turn on camera' i]",

    # Chat
    "chat_button": "button[aria-label*='chat' i], button[aria-label*='Send a message' i], button[data-tooltip*='chat' i]",
    "chat_input": "textarea[aria-label*='message' i], textarea[placeholder*='message' i], div[contenteditable='true'][aria-label*='message' i]",
    "chat_send": "button[aria-label*='Send' i]",

    # Meeting state
    "meeting_ended": (
        "div:has-text('You left the meeting'), div:has-text('meeting has ended'), "
        "div:has-text('removed from the meeting'), div:has-text('You\\'ve been removed'), "
        "div:has-text('The video call has ended'), div:has-text('Return to home screen')"
    ),
    "rejoin_button": (
        "button:has-text('Rejoin'), button:has-text('rejoin'), "
        "a:has-text('Rejoin'), button:has-text('Return to home screen')"
    ),
    "lobby_text": "div:has-text('Asking to be let in'), div:has-text('waiting to be let in'), div:has-text('Someone will let you in soon')",

    # Popups
    "dismiss_popup": "button:has-text('Got it'), button:has-text('Dismiss'), button:has-text('OK')",
    "continue_without_account": "button:has-text('Continue without')",
}


class GoogleMeetDriver(BasePlatformDriver):
    """Google Meet meeting automation — guest join flow (no Google account needed)."""

    async def join(self, meeting_url: str) -> bool:
        self.logger.info(f"Joining Google Meet: {meeting_url}")

        await self.page.goto(meeting_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Dismiss any popups
        await self._click_if_visible(S["dismiss_popup"])

        # Enter name for guest join
        name_entered = False
        for selector in [S["guest_name"], S["name_input"]]:
            if await self._fill_if_visible(selector, self.bot_name, timeout=3000):
                name_entered = True
                self.logger.info(f"Entered name: {self.bot_name}")
                break

        if not name_entered:
            self.logger.warning("Could not find name input — may need Google account")
            # Try to continue anyway in case we're already signed in
            await self._click_if_visible(S["continue_without_account"], timeout=3000)
            await asyncio.sleep(2)
            for selector in [S["guest_name"], S["name_input"]]:
                if await self._fill_if_visible(selector, self.bot_name, timeout=3000):
                    name_entered = True
                    break

        # Turn off mic on preview screen (camera stays ON for avatar)
        await self._click_if_visible(S["mic_toggle"], timeout=2000)
        await asyncio.sleep(1)

        # Click "Ask to join" or "Join now"
        if not await self._click_if_visible(S["ask_to_join"], timeout=5000):
            self.logger.error("Could not find join button")
            return False

        self.logger.info("Clicked join — waiting to be admitted")

        # Wait for lobby admission (up to configured timeout, checked externally)
        await asyncio.sleep(3)

        # Ensure muted after joining (camera stays ON for avatar)
        await self.ensure_muted()

        self.logger.info("Successfully joined Google Meet")
        return True

    async def ensure_muted(self):
        # Check if mic is currently on (the "Turn off" label means it's on)
        if await self._is_visible("[aria-label*='Turn off microphone' i]", timeout=1000):
            await self._click_if_visible(S["mic_button"])
            self.logger.info("Muted microphone")

    async def ensure_camera_off(self):
        if await self._is_visible("[aria-label*='Turn off camera' i]", timeout=1000):
            await self._click_if_visible(S["cam_button"])
            self.logger.info("Turned off camera")

    async def post_chat_message(self, message: str):
        # Open chat panel
        await self._click_if_visible(S["chat_button"], timeout=3000)
        await asyncio.sleep(1)

        # Type message
        chat = self.page.locator(S["chat_input"]).first
        try:
            await chat.wait_for(state="visible", timeout=3000)
            await chat.fill(message)
            await asyncio.sleep(0.5)

            # Try send button, then Enter
            if not await self._click_if_visible(S["chat_send"], timeout=1000):
                await chat.press("Enter")
            self.logger.info("Posted chat message")
        except Exception as e:
            self.logger.warning(f"Could not post chat message: {e}")

    async def detect_meeting_ended(self) -> bool:
        # Check explicit "meeting ended" text indicators
        if await self._is_visible(S["meeting_ended"], timeout=500):
            self.logger.info("Meeting ended: detected end text")
            return True

        # Check for "Rejoin" button — appears after meeting ends
        if await self._is_visible(S["rejoin_button"], timeout=300):
            self.logger.info("Meeting ended: detected Rejoin button")
            return True

        # Check if page navigated away from the meeting
        current_url = self.page.url
        if current_url and not any(
            x in current_url.lower()
            for x in ["meet.google.com"]
        ):
            self.logger.info(f"Meeting ended: page navigated away to {current_url}")
            return True

        return False

    async def is_in_lobby(self) -> bool:
        return await self._is_visible(S["lobby_text"], timeout=500)

    async def leave(self):
        try:
            # Google Meet leave button — the red phone icon
            leave = self.page.locator(
                "button[aria-label*='Leave call' i], button[aria-label*='leave' i], "
                "button[data-tooltip*='Leave call' i]"
            ).first
            await leave.click(timeout=3000)
        except Exception as e:
            self.logger.warning(f"Could not click leave: {e}")
