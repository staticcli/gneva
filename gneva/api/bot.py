"""Meeting bot endpoints — join/leave/status via ElevenLabs phone dial-in or Playwright bot."""

import asyncio
import re
import uuid
import logging
from pydantic import BaseModel, field_validator
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.db import get_db
from gneva.models.user import User
from gneva.models.meeting import Meeting
from gneva.auth import get_current_user
from gneva.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/bot", tags=["bot"])
settings = get_settings()


# ── ElevenLabs Phone Dial-In ────────────────────────────────────────

def _should_use_phone_dialin() -> bool:
    """Check if Twilio + ElevenLabs phone dial-in is configured."""
    return bool(
        settings.twilio_account_sid
        and settings.twilio_auth_token
        and settings.twilio_phone_number
        and settings.elevenlabs_agent_id
        and settings.elevenlabs_api_key
        and settings.app_base_url
    )


async def _dialin_via_twilio(
    phone_number: str,
    conference_id: str,
    meeting_id: str,
) -> dict:
    """Dial into a meeting via Twilio with DTMF conference ID, bridged to ElevenLabs agent.

    Uses Twilio REST API with send_digits to enter the conference ID via DTMF tones,
    then connects audio to ElevenLabs ConvAI agent via WebSocket stream bridge.
    """
    from gneva.bot.twilio_dialin import make_outbound_call

    # Clean phone number to E.164 format
    clean_number = re.sub(r"[^\d+]", "", phone_number)
    if not clean_number.startswith("+"):
        clean_number = "+1" + clean_number

    # Clean conference ID (just digits and #)
    clean_conf_id = re.sub(r"[^\d#]", "", conference_id)

    try:
        result = make_outbound_call(
            to_number=clean_number,
            conference_id=clean_conf_id,
            meeting_id=meeting_id,
        )
        logger.info(
            f"Twilio dial-in initiated: call_sid={result['call_sid']} "
            f"to={clean_number} conf={clean_conf_id}"
        )
        return {
            "success": True,
            "call_sid": result["call_sid"],
        }
    except Exception as e:
        logger.error(f"Twilio dial-in failed: {e}")
        raise HTTPException(status_code=502, detail=f"Phone dial-in failed: {e}")

_background_tasks: set = set()


def _create_background_task(coro):
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(lambda t: (_background_tasks.discard(t), t.exception() if not t.cancelled() and t.exception() else None))
    return task

# BotManager singleton — initialized at app startup
_bot_manager = None


def get_bot_manager():
    if _bot_manager is None:
        raise HTTPException(status_code=503, detail="Bot manager not initialized")
    return _bot_manager


def set_bot_manager(manager):
    global _bot_manager
    _bot_manager = manager


GREETING_MODES = {
    "personalized": None,  # AI-generated based on memory (default)
    "professional": "Hey team, I got notes. Let's get into it.",
    "casual": "Hey everyone. What are we getting into today?",
    "energetic": "Alright, let's go! I'm ready. Notes are on me.",
    "funny": "Oh great, another meeting. Nah I'm kidding, let's do this. What's up?",
    "monday": "Happy Monday. Hope the weekend was good. So what's on deck this week?",
    "friday": "Friday, finally. Let's close things out. What do we need to wrap up?",
    "standup": "Morning. Quick sync — what'd everyone get done, what's blocking?",
    "silent": "",  # Client mode — don't say anything
}


def _parse_meeting_info(text: str) -> dict:
    """Parse a pasted Teams meeting info block to extract URL, dial-in number, and conference ID.

    Handles the standard Teams "Copy meeting info" format:
      +1 267-368-7214,,146538464#
      Phone conference ID: 146 538 464#
      https://teams.microsoft.com/meet/...
    """
    result: dict = {"meeting_url": None, "dialin_number": None, "conference_id": None}

    # Extract Teams meeting URL
    url_match = re.search(r'(https://teams\.microsoft\.com/\S+)', text)
    if url_match:
        result["meeting_url"] = url_match.group(1).rstrip(')')

    # Extract dial-in line: "+1 267-368-7214,,146538464#"
    # The commas separate phone number from conference ID DTMF digits
    dialin_match = re.search(r'(\+[\d\s\-()]+),,(\d[\d\s]*#?)', text)
    if dialin_match:
        result["dialin_number"] = re.sub(r'[^\d+]', '', dialin_match.group(1))
        result["conference_id"] = re.sub(r'[^\d#]', '', dialin_match.group(2))
    else:
        # Try "Phone conference ID: 146 538 464#" format
        conf_match = re.search(r'(?:Phone\s+)?[Cc]onference\s+ID[:\s]+(\d[\d\s]*#?)', text)
        if conf_match:
            result["conference_id"] = re.sub(r'[^\d#]', '', conf_match.group(1))

        # Try standalone phone number with country code
        phone_match = re.search(r'(\+\d[\d\s\-()]{7,})', text)
        if phone_match:
            result["dialin_number"] = re.sub(r'[^\d+]', '', phone_match.group(1))

    return result


class BotJoinRequest(BaseModel):
    meeting_url: str = ""  # can be empty if meeting_info is provided
    platform: str = "auto"  # "auto", "zoom", "google_meet", "teams"
    meeting_title: str | None = None
    bot_name: str | None = None  # override default name
    voice_id: str | None = None  # ElevenLabs voice ID for TTS
    greeting_mode: str = "personalized"  # key from GREETING_MODES
    # Phone dial-in fields (for ElevenLabs ConvAI agent)
    dialin_number: str | None = None  # e.g. "+12673687214"
    conference_id: str | None = None  # e.g. "146538464#"
    # Freeform paste: user pastes Teams "Copy meeting info" text
    meeting_info: str | None = None

    @field_validator("bot_name")
    @classmethod
    def _sanitize_bot_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        # Strip HTML tags
        v = re.sub(r"<[^>]*>", "", v).strip()
        if len(v) > 30:
            raise ValueError("bot_name must be at most 30 characters")
        if not re.fullmatch(r"[A-Za-z0-9 ]*", v):
            raise ValueError("bot_name must contain only alphanumeric characters and spaces")
        return v


class BotJoinResponse(BaseModel):
    meeting_id: str
    bot_id: str
    status: str
    platform: str


class BotLeaveRequest(BaseModel):
    meeting_id: str | None = None
    bot_id: str | None = None


@router.post("/join", response_model=BotJoinResponse)
async def join_meeting(
    req: BotJoinRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send Gneva to join a meeting — via phone dial-in (ElevenLabs) or browser bot."""

    # Parse freeform meeting_info if provided
    if req.meeting_info:
        parsed_info = _parse_meeting_info(req.meeting_info)
        if parsed_info["meeting_url"] and not req.meeting_url:
            req.meeting_url = parsed_info["meeting_url"]
        if parsed_info["dialin_number"] and not req.dialin_number:
            req.dialin_number = parsed_info["dialin_number"]
        if parsed_info["conference_id"] and not req.conference_id:
            req.conference_id = parsed_info["conference_id"]

    if not req.meeting_url:
        raise HTTPException(status_code=400, detail="Could not find a meeting URL. Paste the full Teams meeting info or provide a URL.")

    # S5 fix: Validate meeting_url against known platforms to prevent SSRF
    from urllib.parse import urlparse
    parsed = urlparse(req.meeting_url)
    if parsed.scheme not in ("https", "http"):
        raise HTTPException(status_code=400, detail="Meeting URL must use https")
    allowed_hosts = ["zoom.us", "meet.google.com", "teams.microsoft.com", "teams.live.com", "teams.cloud.microsoft"]
    if not any(parsed.hostname and (parsed.hostname == h or parsed.hostname.endswith("." + h)) for h in allowed_hosts):
        raise HTTPException(status_code=400, detail="Unsupported meeting platform URL")

    # Auto-detect platform from URL
    from gneva.bot.platforms import detect_platform
    try:
        platform = detect_platform(req.meeting_url) if req.platform == "auto" else req.platform
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create meeting record
    meeting = Meeting(
        org_id=user.org_id,
        platform=platform,
        title=req.meeting_title,
        status="joining",
    )
    db.add(meeting)
    await db.flush()

    meeting_id_str = str(meeting.id)

    # ── Path 1: ElevenLabs phone dial-in (preferred for Teams) ──
    # Phone handles voice via Twilio→ElevenLabs; browser bot joins silently
    # for screen capture, captions, and chat monitoring.
    if req.dialin_number and req.conference_id and _should_use_phone_dialin():
        try:
            result = await _dialin_via_twilio(
                phone_number=req.dialin_number,
                conference_id=req.conference_id,
                meeting_id=meeting_id_str,
            )
            bot_id = result.get("call_sid", f"phone-{uuid.uuid4().hex[:8]}")
            meeting.bot_id = bot_id
            meeting.status = "active"
            await db.commit()

            # Also launch a visual-only browser bot for screen capture + captions
            try:
                manager = get_bot_manager()
                visual_bot_id = await manager.join_visual_only(
                    meeting_url=req.meeting_url,
                    meeting_id=meeting_id_str,
                    org_id=str(user.org_id),
                )
                logger.info(
                    f"Hybrid mode: phone={bot_id}, visual_bot={visual_bot_id} "
                    f"for meeting {meeting_id_str}"
                )
            except Exception as e:
                logger.warning(f"Visual-only bot failed (phone still active): {e}")

            return BotJoinResponse(
                meeting_id=meeting_id_str,
                bot_id=bot_id,
                status="joining",
                platform=platform,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Phone dial-in failed, falling back to browser bot: {e}")
            # Fall through to browser bot

    # ── Path 2: Browser bot (Playwright — fallback) ──
    manager = get_bot_manager()

    # Define completion callback to update meeting status
    async def on_bot_complete(bot_id, meeting_id, audio_path, success):
        from gneva.db import async_session_factory
        async with async_session_factory() as session:
            result = await session.execute(
                select(Meeting).where(Meeting.id == uuid.UUID(meeting_id))
            )
            m = result.scalar_one_or_none()
            if m:
                m.status = "processing" if success else "failed"
                m.raw_audio_path = audio_path
                await session.commit()
                if success:
                    from gneva.pipeline.runner import process_meeting
                    _create_background_task(process_meeting(meeting_id))

    # Resolve greeting text from mode
    greeting_mode = req.greeting_mode or "personalized"
    if greeting_mode not in GREETING_MODES:
        raise HTTPException(status_code=400, detail=f"Invalid greeting_mode. Options: {', '.join(GREETING_MODES.keys())}")

    # Launch the bot
    try:
        bot_id = await manager.join(
            meeting_url=req.meeting_url,
            meeting_id=meeting_id_str,
            bot_name=req.bot_name or settings.bot_name,
            on_complete=on_bot_complete,
            voice_id=req.voice_id,
            org_id=str(user.org_id),
            greeting_mode=greeting_mode,
        )
    except RuntimeError as e:
        meeting.status = "failed"
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        meeting.status = "failed"
        logger.error("Bot launch failed: %s", e)
        raise HTTPException(status_code=500, detail="Bot launch failed")

    meeting.bot_id = bot_id
    await db.commit()

    return BotJoinResponse(
        meeting_id=meeting_id_str,
        bot_id=bot_id,
        status="joining",
        platform=platform,
    )


@router.post("/leave")
async def leave_meeting(
    req: BotLeaveRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tell Gneva to leave a meeting."""
    manager = get_bot_manager()

    bot_id = req.bot_id

    # Look up bot_id from meeting_id if not provided
    if not bot_id and req.meeting_id:
        result = await db.execute(
            select(Meeting).where(
                Meeting.id == uuid.UUID(req.meeting_id),
                Meeting.org_id == user.org_id,
            )
        )
        meeting = result.scalar_one_or_none()
        if not meeting or not meeting.bot_id:
            raise HTTPException(status_code=404, detail="Meeting/bot not found")
        bot_id = meeting.bot_id

    if not bot_id:
        raise HTTPException(status_code=400, detail="Provide meeting_id or bot_id")

    # S8 fix: verify bot belongs to user's org when bot_id provided directly
    if req.bot_id and not req.meeting_id:
        result = await db.execute(
            select(Meeting).where(Meeting.bot_id == bot_id, Meeting.org_id == user.org_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Bot not found")

    try:
        await manager.leave(bot_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found")

    return {"status": "leaving", "bot_id": bot_id}


@router.get("/status/{bot_id}")
async def bot_status(
    bot_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the status of a bot."""
    # Verify the bot's meeting belongs to the user's org
    result = await db.execute(
        select(Meeting).where(Meeting.bot_id == bot_id, Meeting.org_id == user.org_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Bot not found")

    manager = get_bot_manager()
    try:
        return manager.status(bot_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found")


@router.get("/active")
async def list_active_bots(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all active and recent bots."""
    # Get bot_ids that belong to the user's org
    result = await db.execute(
        select(Meeting.bot_id).where(
            Meeting.org_id == user.org_id,
            Meeting.bot_id.isnot(None),
        )
    )
    org_bot_ids = {row[0] for row in result.all()}

    manager = get_bot_manager()
    all_bots = manager.list_bots()
    # Filter to only bots belonging to this org
    org_bots = [b for b in all_bots if b.get("bot_id") in org_bot_ids]
    return {"bots": org_bots}


@router.get("/greeting-modes")
async def list_greeting_modes(user: User = Depends(get_current_user)):
    """List available greeting modes for bot join."""
    modes = []
    labels = {
        "personalized": "Personalized (AI picks based on memory)",
        "professional": "Professional",
        "casual": "Casual & Friendly",
        "energetic": "Energetic & Pumped",
        "funny": "Funny / Sarcastic",
        "monday": "Monday Vibes",
        "friday": "Friday Energy",
        "standup": "Standup / Daily Sync",
        "silent": "Silent (Client Mode)",
    }
    for key in GREETING_MODES:
        modes.append({
            "id": key,
            "label": labels.get(key, key.title()),
            "preview": GREETING_MODES[key] if GREETING_MODES[key] else ("(AI-generated)" if key == "personalized" else "(no greeting)"),
        })
    return {"modes": modes}


@router.get("/debug/{bot_id}")
async def bot_debug(
    bot_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Debug endpoint — dump caption DOM and JS state from the bot's browser."""
    # Verify the bot's meeting belongs to user's org
    result = await db.execute(
        select(Meeting).where(Meeting.bot_id == bot_id, Meeting.org_id == user.org_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Bot not found")

    manager = get_bot_manager()
    bot = manager._bots.get(bot_id)
    if not bot or not bot._page:
        raise HTTPException(status_code=404, detail="Bot not found or no page")

    try:
        result = await bot._page.evaluate("""
            (() => {
                const info = {};

                // Get caption-related elements
                const captionEls = document.querySelectorAll('[data-tid*="caption"], [class*="caption" i], [class*="Caption"]');
                info.captionElementCount = captionEls.length;
                info.captionElements = [];
                captionEls.forEach((el, i) => {
                    if (i < 20) {
                        info.captionElements.push({
                            tag: el.tagName,
                            classes: el.className ? el.className.substring(0, 200) : '',
                            dataTid: el.getAttribute('data-tid') || '',
                            text: (el.textContent || '').substring(0, 200),
                            childCount: el.children.length,
                            innerHTML: el.innerHTML.substring(0, 500)
                        });
                    }
                });

                // Check pending captions
                info.pendingSegments = window.__gnevaCaptions ? window.__gnevaCaptions.segments.length : -1;

                // Audio capture diagnostics
                info.audioCtxExists = !!window.__gnevaAudioCaptureCtx;
                info.audioCtxState = window.__gnevaAudioCaptureCtx ? window.__gnevaAudioCaptureCtx.state : 'none';
                info.mergerExists = !!window.__gnevaAudioCaptureMerger;
                info.incomingTracks = window.__gnevaIncomingAudioTracks ? window.__gnevaIncomingAudioTracks.length : 0;
                info.mediaElements = document.querySelectorAll('audio, video').length;

                // Get the full visible caption text
                const captionPanel = document.querySelector(
                    '[data-tid="closed-captions-renderer"], [class*="captionPanel" i], [class*="closedCaptions" i]'
                );
                info.captionPanelFound = !!captionPanel;
                info.captionPanelText = captionPanel ? captionPanel.innerText.substring(0, 1000) : 'NOT FOUND';

                return info;
            })()
        """)
        return result
    except Exception as e:
        return {"error": str(e)}
