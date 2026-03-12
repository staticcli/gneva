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

    def _update_status(self, msg: str):
        """Update the bot's status_message if we have a reference to the bot."""
        if hasattr(self, '_bot') and self._bot:
            self._bot.status_message = msg

    async def join(self, meeting_url: str) -> bool:
        self.logger.info(f"Joining Teams meeting: {meeting_url}")
        self._update_status("Loading Teams meeting page...")

        # Inject JS BEFORE navigation to block protocol handlers (msteams://, ms-teams://)
        # This prevents the OS-level "open Teams app?" popup
        await self.page.add_init_script("""
            // Block msteams:// protocol navigations
            const origAssign = Object.getOwnPropertyDescriptor(Location.prototype, 'assign');
            const origReplace = Object.getOwnPropertyDescriptor(Location.prototype, 'replace');
            const origHref = Object.getOwnPropertyDescriptor(Location.prototype, 'href');

            function blockProtocol(url) {
                if (typeof url === 'string' && (url.startsWith('msteams:') || url.startsWith('ms-teams:'))) {
                    console.log('[Gneva] Blocked protocol navigation:', url.substring(0, 30));
                    return true;
                }
                return false;
            }

            // Override window.open to block protocol URLs
            const origOpen = window.open;
            window.open = function(url, ...args) {
                if (blockProtocol(url)) return null;
                return origOpen.call(this, url, ...args);
            };

            // Override location.href setter
            if (origHref && origHref.set) {
                Object.defineProperty(Location.prototype, 'href', {
                    get: origHref.get,
                    set: function(url) {
                        if (blockProtocol(url)) return;
                        origHref.set.call(this, url);
                    },
                    configurable: true,
                });
            }

            // Override location.assign
            if (origAssign && origAssign.value) {
                Location.prototype.assign = function(url) {
                    if (blockProtocol(url)) return;
                    origAssign.value.call(this, url);
                };
            }

            // Override location.replace
            if (origReplace && origReplace.value) {
                Location.prototype.replace = function(url) {
                    if (blockProtocol(url)) return;
                    origReplace.value.call(this, url);
                };
            }

            // Block iframe-based protocol launches
            const origCreateElement = document.createElement.bind(document);
            document.createElement = function(tag, ...args) {
                const el = origCreateElement(tag, ...args);
                if (tag.toLowerCase() === 'iframe') {
                    const origSrcDesc = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'src');
                    if (origSrcDesc) {
                        Object.defineProperty(el, 'src', {
                            get: origSrcDesc.get,
                            set: function(url) {
                                if (blockProtocol(url)) return;
                                origSrcDesc.set.call(this, url);
                            },
                            configurable: true,
                        });
                    }
                }
                return el;
            };

            console.log('[Gneva] Protocol handler blocker installed');
        """)

        await self.page.goto(meeting_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Accept cookies
        await self._click_if_visible(S["cookie_accept"])
        await asyncio.sleep(1)

        # Click "Continue on this browser" to use web client
        self._update_status("Selecting web browser client...")
        if await self._click_if_visible(S["continue_browser"], timeout=8000):
            self.logger.info("Selected web browser client")
        else:
            self.logger.warning("Could not find 'Continue on browser' — trying to proceed")

        # Light-meetings takes longer to load (~15-20s)
        self._update_status("Waiting for pre-join screen...")
        self.logger.info("Waiting for pre-join screen to load...")
        await asyncio.sleep(15)

        # Check if we're already in the meeting (light-meetings can auto-join)
        if await self._is_already_in_meeting():
            self.logger.info("Already in the meeting (auto-joined via light-meetings)")
            await self.ensure_muted()
            return True

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

        # Ensure camera is ON on pre-join screen so Teams calls getUserMedia({video: true})
        # Our avatar JS intercepts this and serves the canvas stream
        cam_off_sel = "button[aria-label*='Turn on camera' i], button[aria-label*='Turn camera on' i], toggle-button[aria-label*='Camera' i][aria-checked='false']"
        if await self._click_if_visible(cam_off_sel, timeout=2000):
            self.logger.info("Turned camera ON (for avatar injection)")
            await asyncio.sleep(1)

        # Enter bot name
        self._update_status(f"Entering name: {self.bot_name}...")
        if await self._fill_if_visible(S["name_input"], self.bot_name, timeout=5000):
            self.logger.info(f"Entered name: {self.bot_name}")
        else:
            self.logger.warning("Could not find name input")

        await asyncio.sleep(1)

        # Click "Join now"
        self._update_status("Clicking Join Now...")
        if not await self._click_if_visible(S["join_button"], timeout=5000):
            # One more check — maybe we got auto-joined while setting up
            if await self._is_already_in_meeting():
                self.logger.info("Auto-joined while preparing (no join button needed)")
                await self.ensure_muted()
                return True
            self.logger.error("Could not find join button")
            return False

        self._update_status("Joined — configuring audio...")
        self.logger.info("Clicked join — may be in lobby")
        await asyncio.sleep(5)

        # Ensure mic muted (keep camera ON for avatar)
        await self.ensure_muted()

        self._update_status("Successfully joined Teams meeting!")
        self.logger.info("Successfully joined Teams meeting")
        return True

    async def _is_already_in_meeting(self) -> bool:
        """Detect if we're already inside a Teams meeting (light-meetings auto-join)."""
        # Leave button is the most reliable indicator of being in-meeting
        leave_sel = "button[aria-label*='Leave' i], button:has-text('Leave'), button[id*='hangup' i]"
        if await self._is_visible(leave_sel, timeout=2000):
            return True
        # Also check for meeting toolbar indicators
        toolbar_sel = (
            "button[aria-label*='Mute' i], button[aria-label*='Unmute' i], "
            "button[aria-label*='Camera' i], button[aria-label*='More actions' i]"
        )
        if await self._is_visible(toolbar_sel, timeout=1000):
            return True
        return False

    async def ensure_muted(self):
        if await self._is_visible(S["mic_on_indicator"], timeout=1000):
            await self._click_if_visible(S["mic_button"])
            self.logger.info("Muted microphone")

    async def ensure_unmuted(self):
        """Unmute microphone — click the unmute button if currently muted."""
        unmute_sel = "button[aria-label*='Unmute' i], button[aria-label*='Turn on microphone' i]"
        if await self._is_visible(unmute_sel, timeout=1000):
            await self._click_if_visible(unmute_sel)
            self.logger.info("Unmuted microphone")

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

    async def enable_live_captions(self):
        """Turn on Teams live captions so we can read what participants say."""
        # Try the "More" / "..." menu first (captions is usually there)
        more_sel = (
            "button[aria-label*='More actions' i], button[aria-label*='More' i], "
            "button[id*='more-button' i], button[data-tid='more-button'], "
            "button[aria-label*='more options' i]"
        )
        if await self._click_if_visible(more_sel, timeout=3000):
            self.logger.info("Opened 'More actions' menu")
            await asyncio.sleep(1)

            # Look for "Turn on live captions" or "Language and speech" > captions
            captions_sel = (
                "button:has-text('Turn on live captions'), "
                "button:has-text('Live captions'), "
                "span:has-text('Turn on live captions'), "
                "li:has-text('Turn on live captions'), "
                "div[role='menuitem']:has-text('captions'), "
                "button[aria-label*='captions' i], "
                "div[role='menuitemcheckbox']:has-text('Live captions'), "
                "span:has-text('Live captions')"
            )
            if await self._click_if_visible(captions_sel, timeout=3000):
                self.logger.info("Enabled live captions")
                await asyncio.sleep(1)
                # Dismiss any "captions language" dialog
                await self._click_if_visible(
                    "button:has-text('Confirm'), button:has-text('Got it'), button:has-text('OK')",
                    timeout=2000,
                )
                return True
            else:
                self.logger.warning("Could not find 'Turn on live captions' in menu")
                # Close the menu by pressing Escape
                try:
                    await self.page.keyboard.press("Escape")
                except Exception:
                    pass
        else:
            self.logger.warning("Could not find 'More actions' button for captions")

        # Fallback: try direct caption button (some Teams versions show it in toolbar)
        direct_sel = (
            "button[aria-label*='caption' i], "
            "button[aria-label*='Caption' i], "
            "button[data-tid='toggle-captions']"
        )
        if await self._click_if_visible(direct_sel, timeout=2000):
            self.logger.info("Enabled live captions (direct button)")
            await asyncio.sleep(1)
            await self._click_if_visible(
                "button:has-text('Confirm'), button:has-text('Got it')",
                timeout=2000,
            )
            return True

        self.logger.warning("Could not enable live captions")
        return False

    async def leave(self):
        try:
            leave = self.page.locator(
                "button[aria-label*='Leave' i], button:has-text('Leave'), button[id*='hangup' i]"
            ).first
            await leave.click(timeout=3000)
        except Exception as e:
            self.logger.warning(f"Could not click leave: {e}")
