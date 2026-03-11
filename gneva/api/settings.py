"""Settings API — org configuration, voice management."""

import logging
import uuid

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.auth import get_current_user
from gneva.config import get_settings
from gneva.db import get_db
from gneva.models.user import Organization

router = APIRouter(prefix="/api/settings", tags=["settings"])
settings = get_settings()

# In-memory voice store (per org) — in production, store in DB
_voice_store: dict[str, list[dict]] = {}

# Default voices from config
_DEFAULT_VOICES = [
    {"id": "OUBnvvuqEKdDWtapoJFn", "name": "Patel", "provider": "elevenlabs", "is_default": True},
    {"id": "56bWURjYFHyYyVf490Dp", "name": "Emma", "provider": "elevenlabs", "is_default": False},
]


def _get_voices(org_id: str) -> list[dict]:
    if org_id not in _voice_store:
        _voice_store[org_id] = [dict(v) for v in _DEFAULT_VOICES]  # B4 fix: deep copy
    return _voice_store[org_id]


import re

def _validate_voice_id(voice_id: str) -> str:
    """S6 fix: validate voice_id format to prevent path traversal."""
    if not re.match(r'^[a-zA-Z0-9]{10,30}$', voice_id):
        raise HTTPException(status_code=400, detail="Invalid voice ID format")
    return voice_id


class VoiceCreate(BaseModel):
    voice_id: str
    name: str
    provider: str = "elevenlabs"


class VoiceUpdate(BaseModel):
    is_default: bool | None = None
    name: str | None = None


@router.get("/")
async def get_settings_endpoint(user=Depends(get_current_user)):
    """Return current org settings."""
    voices = _get_voices(str(user.org_id))
    default_voice = next((v for v in voices if v.get("is_default")), voices[0] if voices else None)
    return {
        "bot_name": settings.bot_name,
        "bot_consent_message": settings.bot_consent_message,
        "tts_backend": settings.tts_backend,
        "scheduler_enabled": settings.scheduler_enabled,
        "google_calendar_enabled": settings.google_calendar_enabled,
        "outlook_calendar_enabled": settings.outlook_calendar_enabled,
        "elevenlabs_configured": bool(settings.elevenlabs_api_key),
        "default_voice": default_voice,
    }


# ------------------------------------------------------------------
# Voice Management
# ------------------------------------------------------------------
@router.get("/voices")
async def list_voices(user=Depends(get_current_user)):
    """List all configured voices for the org."""
    voices = _get_voices(str(user.org_id))
    return {"voices": voices}


@router.post("/voices")
async def add_voice(req: VoiceCreate, user=Depends(get_current_user)):
    """Add a new voice option."""
    _validate_voice_id(req.voice_id)
    voices = _get_voices(str(user.org_id))

    # Check for duplicate
    if any(v["id"] == req.voice_id for v in voices):
        raise HTTPException(status_code=409, detail="Voice already exists")

    new_voice = {
        "id": req.voice_id,
        "name": req.name,
        "provider": req.provider,
        "is_default": len(voices) == 0,
    }
    voices.append(new_voice)
    return {"status": "added", "voice": new_voice, "voices": voices}


@router.patch("/voices/{voice_id}")
async def update_voice(voice_id: str, req: VoiceUpdate, user=Depends(get_current_user)):
    """Update a voice (set as default, rename)."""
    voices = _get_voices(str(user.org_id))
    voice = next((v for v in voices if v["id"] == voice_id), None)
    if not voice:
        raise HTTPException(status_code=404, detail="Voice not found")

    if req.is_default is True:
        # Unset all others
        for v in voices:
            v["is_default"] = False
        voice["is_default"] = True

    if req.name is not None:
        voice["name"] = req.name

    return {"status": "updated", "voice": voice, "voices": voices}


@router.delete("/voices/{voice_id}")
async def delete_voice(voice_id: str, user=Depends(get_current_user)):
    """Remove a voice option."""
    voices = _get_voices(str(user.org_id))
    _voice_store[str(user.org_id)] = [v for v in voices if v["id"] != voice_id]
    voices = _get_voices(str(user.org_id))

    # Ensure at least one default
    if voices and not any(v.get("is_default") for v in voices):
        voices[0]["is_default"] = True

    return {"status": "deleted", "voices": voices}


@router.post("/voices/{voice_id}/preview")
async def preview_voice(voice_id: str, user=Depends(get_current_user)):
    """Generate a short TTS preview of a voice."""
    try:
        from gneva.services.tts import TTSService
        import base64
        tts = TTSService()
        # Override voice ID for preview
        tts._el_voice = voice_id
        audio = await tts.synthesize("Hi, I'm Gneva, your AI team member. Nice to meet you!")
        audio_b64 = base64.b64encode(audio).decode()
        return {"audio": audio_b64, "format": "wav"}
    except Exception as e:
        logger.error(f"Voice preview failed for {voice_id}: {e}")
        raise HTTPException(status_code=502, detail="Voice preview failed")
