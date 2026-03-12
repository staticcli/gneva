"""Screen capture engine — gives Gneva visual awareness of shared content.

Periodically captures screenshots during meetings, detects screen sharing,
and uses Claude's vision API to understand what's being shown. The visual
context is fed into the conversation engine so Gneva can reference on-screen
content naturally.
"""

import asyncio
import base64
import hashlib
import logging
import time

logger = logging.getLogger(__name__)


class ScreenCaptureEngine:
    """Captures and analyzes meeting screen content for visual awareness."""

    def __init__(self, page, org_id: str | None = None):
        self._page = page
        self._org_id = org_id
        self._running = False
        self._task: asyncio.Task | None = None

        # Visual context — rolling summary of what's on screen
        self._visual_context: str = ""
        self._visual_history: list[dict] = []  # last N analyses
        self._max_history = 5

        # Screen sharing state
        self._screen_sharing_active = False
        self._last_sharing_change = 0

        # Deduplication
        self._last_screenshot_hash: str | None = None

        # Timing
        self._capture_interval_sharing = 15   # seconds when screen sharing
        self._capture_interval_normal = 60    # seconds when no sharing
        self._max_analyses_per_minute = 4
        self._recent_analyses: list[float] = []  # timestamps of recent analyses

    async def start(self):
        """Start the screen capture loop."""
        self._running = True
        self._task = asyncio.create_task(self._capture_loop())
        logger.info("Screen capture engine started")

    async def stop(self):
        """Stop the screen capture loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Screen capture engine stopped")

    @property
    def visual_context(self) -> str:
        """Current visual context for the conversation engine."""
        return self._visual_context

    @property
    def is_screen_sharing(self) -> bool:
        return self._screen_sharing_active

    async def capture_and_analyze_now(self) -> str | None:
        """Force an immediate capture and analysis. Used by the describe_screen tool."""
        try:
            screenshot = await self._take_screenshot()
            if not screenshot:
                return None
            return await self._analyze_screenshot(screenshot)
        except Exception as e:
            logger.warning(f"Immediate capture failed: {e}")
            return None

    async def _capture_loop(self):
        """Main capture loop — runs throughout the meeting."""
        # Wait for meeting to stabilize before starting captures
        try:
            await asyncio.sleep(15)
        except asyncio.CancelledError:
            return

        while self._running:
            try:
                # Detect screen sharing state
                sharing = await self._detect_screen_sharing()
                if sharing != self._screen_sharing_active:
                    self._screen_sharing_active = sharing
                    self._last_sharing_change = time.time()
                    logger.info(
                        f"Screen sharing {'started' if sharing else 'ended'}"
                    )
                    # Force immediate capture on sharing state change
                    if sharing:
                        await self._capture_and_process()

                # Choose interval based on sharing state
                interval = (
                    self._capture_interval_sharing
                    if self._screen_sharing_active
                    else self._capture_interval_normal
                )

                await asyncio.sleep(interval)

                if not self._running:
                    break

                # Only capture during screen sharing or periodically
                if self._screen_sharing_active:
                    await self._capture_and_process()
                elif time.time() - self._last_sharing_change > 120:
                    # Periodic ambient capture when no sharing (every 60s)
                    await self._capture_and_process()

            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.debug(f"Screen capture loop error: {e}")
                await asyncio.sleep(10)

    async def _capture_and_process(self):
        """Take screenshot, check for changes, analyze if new."""
        # Rate limit
        now = time.time()
        self._recent_analyses = [
            t for t in self._recent_analyses if now - t < 60
        ]
        if len(self._recent_analyses) >= self._max_analyses_per_minute:
            return

        screenshot = await self._take_screenshot()
        if not screenshot:
            return

        # Dedup — skip if screenshot hasn't changed
        img_hash = hashlib.md5(screenshot).hexdigest()
        if img_hash == self._last_screenshot_hash:
            return
        self._last_screenshot_hash = img_hash

        # Analyze
        description = await self._analyze_screenshot(screenshot)
        if description:
            self._recent_analyses.append(time.time())
            self._visual_history.append({
                "time": time.time(),
                "description": description,
                "sharing": self._screen_sharing_active,
            })
            if len(self._visual_history) > self._max_history:
                self._visual_history = self._visual_history[-self._max_history:]

            # Build rolling context from recent analyses
            self._visual_context = self._build_context()

    async def _take_screenshot(self) -> bytes | None:
        """Capture a screenshot from the meeting page."""
        try:
            # Use JPEG for smaller payload (vision API still works fine)
            screenshot = await self._page.screenshot(
                type="jpeg",
                quality=60,
                timeout=5000,
            )
            return screenshot
        except Exception as e:
            logger.debug(f"Screenshot failed: {e}")
            return None

    async def _detect_screen_sharing(self) -> bool:
        """Detect if someone is sharing their screen in the meeting."""
        try:
            result = await self._page.evaluate("""
                (() => {
                    // Teams screen sharing indicators
                    const teamsShare = document.querySelector(
                        '[data-tid*="content-share"], [data-tid*="screen-share"], ' +
                        '[class*="screenShare" i], [class*="contentShare" i], ' +
                        '[aria-label*="is presenting" i], [aria-label*="is sharing" i], ' +
                        '[data-cid="sharing-stage"], [class*="sharingStage" i]'
                    );
                    if (teamsShare) return true;

                    // Google Meet screen sharing
                    const meetShare = document.querySelector(
                        '[data-self-name*="presentation" i], ' +
                        '[jsname*="presentation" i], ' +
                        '[class*="screenShare" i]'
                    );
                    if (meetShare) return true;

                    // Zoom screen sharing
                    const zoomShare = document.querySelector(
                        '[class*="sharing-content" i], ' +
                        '[class*="screen-share" i], ' +
                        '[aria-label*="shared screen" i]'
                    );
                    if (zoomShare) return true;

                    // Generic: look for large video elements that might be screen shares
                    // (screen shares are typically larger than webcam feeds)
                    const videos = document.querySelectorAll('video');
                    for (const v of videos) {
                        const rect = v.getBoundingClientRect();
                        if (rect.width > 800 && rect.height > 400) {
                            return true;
                        }
                    }

                    return false;
                })()
            """)
            return bool(result)
        except Exception:
            return False

    async def _analyze_screenshot(self, screenshot_bytes: bytes) -> str | None:
        """Analyze a screenshot using Claude's vision API."""
        try:
            from gneva.services import get_anthropic_client
            client = get_anthropic_client()

            b64 = base64.b64encode(screenshot_bytes).decode()

            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "You are looking at a meeting screen. Describe what's being "
                                "shared in 2-3 concise sentences. Focus on: slide content, "
                                "charts, data, code, documents, spreadsheets, or diagrams. "
                                "Note any specific numbers, names, or data points visible. "
                                "If it's just webcam feeds and no screen share, say 'No content "
                                "being shared, just video feeds.' Be factual and brief."
                            ),
                        },
                    ],
                }],
            )
            result = response.content[0].text.strip()
            logger.info(f"Screen analysis: {result[:80]}...")
            return result

        except Exception as e:
            logger.warning(f"Screenshot analysis failed: {e}")
            return None

    def _build_context(self) -> str:
        """Build a rolling visual context string from recent analyses."""
        if not self._visual_history:
            return ""

        # Use the most recent analysis as primary context
        latest = self._visual_history[-1]
        context = latest["description"]

        # If there are older entries, note what changed
        if len(self._visual_history) >= 2:
            prev = self._visual_history[-2]
            if prev["description"] != latest["description"]:
                context += f"\n(Previously showing: {prev['description'][:100]})"

        return context

    async def describe_now(self) -> str:
        """On-demand screenshot + vision analysis. Returns description string."""
        screenshot = await self._take_screenshot()
        if not screenshot:
            return "Could not capture the screen right now."
        description = await self._analyze_screenshot(screenshot)
        if not description:
            return "Captured the screen but couldn't analyze it."
        # Update context
        self._visual_history.append({
            "time": time.time(),
            "description": description,
            "sharing": self._screen_sharing_active,
        })
        if len(self._visual_history) > self._max_history:
            self._visual_history.pop(0)
        self._visual_context = self._build_context()
        return description
