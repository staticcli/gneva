"""Settings API — non-sensitive org configuration."""

from fastapi import APIRouter, Depends

from gneva.auth import get_current_user
from gneva.config import get_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])
settings = get_settings()


@router.get("/")
async def get_settings_endpoint(user=Depends(get_current_user)):
    """Return current org settings."""
    return {
        "bot_name": settings.bot_name,
        "bot_consent_message": settings.bot_consent_message,
        "tts_backend": settings.tts_backend,
        "scheduler_enabled": settings.scheduler_enabled,
        "google_calendar_enabled": settings.google_calendar_enabled,
        "outlook_calendar_enabled": settings.outlook_calendar_enabled,
    }
