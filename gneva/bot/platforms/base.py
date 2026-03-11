"""Base platform driver — abstract interface for all meeting platforms."""

from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BasePlatformDriver(ABC):
    """Abstract base for platform-specific meeting automation."""

    def __init__(self, page, bot_name: str):
        self.page = page
        self.bot_name = bot_name
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    async def join(self, meeting_url: str) -> bool:
        """Navigate to the meeting URL and join. Returns True if successfully joined."""
        ...

    @abstractmethod
    async def ensure_muted(self):
        """Mute the microphone."""
        ...

    @abstractmethod
    async def ensure_unmuted(self):
        """Unmute the microphone."""
        ...

    @abstractmethod
    async def ensure_camera_off(self):
        """Turn off the camera."""
        ...

    @abstractmethod
    async def post_chat_message(self, message: str):
        """Send a message in the meeting chat."""
        ...

    @abstractmethod
    async def detect_meeting_ended(self) -> bool:
        """Check if the meeting has ended."""
        ...

    @abstractmethod
    async def is_in_lobby(self) -> bool:
        """Check if we're waiting in a lobby."""
        ...

    @abstractmethod
    async def leave(self):
        """Leave the meeting gracefully."""
        ...

    async def _click_if_visible(self, selector: str, timeout: int = 3000) -> bool:
        """Try to click an element if it's visible within timeout. Returns True if clicked."""
        try:
            loc = self.page.locator(selector).first
            await loc.wait_for(state="visible", timeout=timeout)
            await loc.click()
            return True
        except Exception:
            return False

    async def _fill_if_visible(self, selector: str, text: str, timeout: int = 3000) -> bool:
        """Try to fill an input if visible. Returns True if filled."""
        try:
            loc = self.page.locator(selector).first
            await loc.wait_for(state="visible", timeout=timeout)
            await loc.fill(text)
            return True
        except Exception:
            return False

    async def _is_visible(self, selector: str, timeout: int = 1000) -> bool:
        """Check if an element is visible."""
        try:
            loc = self.page.locator(selector).first
            await loc.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False
