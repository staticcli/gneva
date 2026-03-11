"""Platform drivers for meeting bot — auto-detect platform from URL."""

from gneva.bot.platforms.base import BasePlatformDriver
from gneva.bot.platforms.zoom import ZoomDriver
from gneva.bot.platforms.google_meet import GoogleMeetDriver
from gneva.bot.platforms.teams import TeamsDriver


def detect_platform(url: str) -> str:
    """Detect meeting platform from URL."""
    url_lower = url.lower()
    if "zoom.us" in url_lower or "zoomgov.com" in url_lower:
        return "zoom"
    elif "meet.google.com" in url_lower:
        return "google_meet"
    elif "teams.microsoft.com" in url_lower or "teams.live.com" in url_lower:
        return "teams"
    else:
        raise ValueError(f"Unsupported meeting URL: {url}")


def get_driver(platform: str, page, bot_name: str) -> BasePlatformDriver:
    """Get the appropriate platform driver."""
    drivers = {
        "zoom": ZoomDriver,
        "google_meet": GoogleMeetDriver,
        "teams": TeamsDriver,
    }
    driver_cls = drivers.get(platform)
    if not driver_cls:
        raise ValueError(f"Unsupported platform: {platform}")
    return driver_cls(page=page, bot_name=bot_name)


__all__ = [
    "BasePlatformDriver",
    "ZoomDriver",
    "GoogleMeetDriver",
    "TeamsDriver",
    "detect_platform",
    "get_driver",
]
