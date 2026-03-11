"""Slack API routes — events, commands, interactive components, OAuth."""

import hashlib
import hmac
import logging
import time

from fastapi import APIRouter, Request, HTTPException, Response
from pydantic import BaseModel

from sqlalchemy import select

from gneva.config import get_settings
from gneva.db import async_session_factory
from gneva.models.user import Organization
from gneva.services.slack import SlackService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/slack", tags=["slack"])

_slack_service: SlackService | None = None


def _get_slack() -> SlackService:
    global _slack_service
    if _slack_service is None:
        _slack_service = SlackService()
    return _slack_service


def _verify_slack_request(body: bytes, timestamp: str, signature: str) -> bool:
    """Verify that the request came from Slack using signing secret."""
    if not settings.slack_signing_secret:
        logger.warning("Slack signing secret not configured — rejecting request")
        return False
    try:
        ts = float(timestamp)
    except (ValueError, TypeError):
        return False
    if abs(time.time() - ts) > 300:
        return False
    base = f"v0:{timestamp}:{body.decode('utf-8')}"
    expected = "v0=" + hmac.new(
        settings.slack_signing_secret.encode(), base.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ------------------------------------------------------------------
# Events API
# ------------------------------------------------------------------
@router.post("/events")
async def slack_events(request: Request):
    """Slack Events API endpoint — handles URL verification challenge and events."""
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "0")
    signature = request.headers.get("X-Slack-Signature", "")

    if not _verify_slack_request(body, timestamp, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    payload = await request.json()

    # URL verification challenge
    if payload.get("type") == "url_verification":
        return {"challenge": payload["challenge"]}

    # Event dispatch
    event_type = payload.get("event", {}).get("type")
    if event_type == "app_mention":
        text = payload["event"].get("text", "")
        channel = payload["event"].get("channel", "")
        user_id = payload["event"].get("user", "")
        # Strip the bot mention prefix
        clean_text = text.split(">", 1)[-1].strip() if ">" in text else text
        slack = _get_slack()
        # TODO: Map Slack workspace (team_id) to org_id properly
        org_id = ""
        async with async_session_factory() as db:
            org = (await db.execute(select(Organization).limit(1))).scalar_one_or_none()
            if org:
                org_id = str(org.id)
        result = await slack.handle_slash_command(f"ask {clean_text}", user_id, channel, org_id=org_id)
        if result.get("text"):
            await slack._post_message(channel, text=result["text"])

    elif event_type == "message":
        # Could handle DM conversations here
        pass

    return Response(status_code=200)


# ------------------------------------------------------------------
# Slash commands
# ------------------------------------------------------------------
@router.post("/commands")
async def slack_commands(request: Request):
    """Handle /gneva slash commands from Slack."""
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "0")
    signature = request.headers.get("X-Slack-Signature", "")

    if not _verify_slack_request(body, timestamp, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    form = await request.form()
    text = form.get("text", "")
    user_id = form.get("user_id", "")
    channel_id = form.get("channel_id", "")

    slack = _get_slack()
    # TODO: Map Slack workspace (team_id from form) to org_id properly
    org_id = ""
    async with async_session_factory() as db:
        org = (await db.execute(select(Organization).limit(1))).scalar_one_or_none()
        if org:
            org_id = str(org.id)
    response = await slack.handle_slash_command(str(text), str(user_id), str(channel_id), org_id=org_id)
    return response


# ------------------------------------------------------------------
# Interactive components (buttons, menus, modals)
# ------------------------------------------------------------------
@router.post("/interact")
async def slack_interact(request: Request):
    """Handle Slack interactive component payloads (buttons, menus, etc.)."""
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "0")
    signature = request.headers.get("X-Slack-Signature", "")

    if not _verify_slack_request(body, timestamp, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    import json
    form = await request.form()
    payload_str = form.get("payload", "{}")
    payload = json.loads(str(payload_str))

    action_type = payload.get("type")

    if action_type == "block_actions":
        for action in payload.get("actions", []):
            action_id = action.get("action_id", "")
            logger.info("Slack interactive action: %s", action_id)
            # Handle specific button clicks here (e.g., complete action item)

    elif action_type == "view_submission":
        # Handle modal submissions
        pass

    return Response(status_code=200)


# ------------------------------------------------------------------
# OAuth install flow
# ------------------------------------------------------------------
@router.get("/install")
async def slack_install():
    """Generate Slack OAuth install URL."""
    if not settings.slack_bot_token:
        raise HTTPException(status_code=503, detail="Slack not configured")

    if not settings.slack_client_id:
        raise HTTPException(status_code=503, detail="Slack OAuth not configured (missing client_id)")

    client_id = settings.slack_client_id
    scopes = "chat:write,commands,app_mentions:read,im:write,channels:read"
    install_url = (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={client_id}"
        f"&scope={scopes}"
        f"&redirect_uri={settings.cors_origins[0] if settings.cors_origins else 'http://localhost:8000'}/api/slack/callback"
    )
    return {"install_url": install_url}


@router.get("/callback")
async def slack_callback(code: str = ""):
    """Handle Slack OAuth callback — exchange code for bot token."""
    if not code:
        raise HTTPException(status_code=400, detail="Missing OAuth code")

    # In production: exchange code for access token via oauth.v2.access
    # Store the bot token per-workspace in the database
    import httpx
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "code": code,
                "client_id": settings.slack_client_id,
                "client_secret": settings.slack_client_secret,
            },
            timeout=10,
        )
        data = resp.json()

    if not data.get("ok"):
        raise HTTPException(status_code=400, detail=f"Slack OAuth failed: {data.get('error')}")

    # In production: store data["access_token"] and data["team"]["id"] in DB
    return {
        "status": "installed",
        "team": data.get("team", {}).get("name"),
        "team_id": data.get("team", {}).get("id"),
    }
