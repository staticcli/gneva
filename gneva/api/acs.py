"""ACS Call Automation webhook endpoints.

Receives callback events from Azure Communication Services and routes them
to the appropriate ACSBot instance. Also serves as a health-check for the
ACS callback URL.
"""

import logging
from fastapi import APIRouter, Request, Response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/acs", tags=["acs"])


@router.post("/events")
async def acs_events(request: Request):
    """Receive ACS Call Automation webhook events.

    ACS sends events as JSON arrays. Each event has:
    - type: event type (e.g., "Microsoft.Communication.CallConnected")
    - data: event-specific payload
    - subject: call connection ID

    We route each event to the matching ACSBot instance via the BotManager.
    """
    try:
        body = await request.json()
    except Exception:
        return Response(status_code=400)

    # ACS sends events as an array
    events = body if isinstance(body, list) else [body]

    for event in events:
        # Handle Azure EventGrid validation handshake
        event_type = event.get("eventType", "")
        if event_type == "Microsoft.EventGrid.SubscriptionValidationEvent":
            validation_code = event.get("data", {}).get("validationCode", "")
            logger.info(f"ACS EventGrid validation request — code: {validation_code}")
            return {"validationResponse": validation_code}

        # Route the event to the right bot
        call_connection_id = event.get("data", {}).get("callConnectionId", "")
        if not call_connection_id:
            # Try alternate location
            call_connection_id = event.get("subject", "")

        if call_connection_id:
            await _route_event_to_bot(call_connection_id, event)
        else:
            logger.debug(f"ACS event without callConnectionId: {event.get('type', 'unknown')}")

    return Response(status_code=200)


async def _route_event_to_bot(call_connection_id: str, event: dict):
    """Find the ACSBot with the matching call_connection_id and deliver the event."""
    from gneva.api.bot import get_bot_manager

    try:
        manager = get_bot_manager()
    except Exception:
        logger.warning("ACS event received but BotManager not initialized")
        return

    # Search through active bots for the matching ACSBot
    for bot_id, bot in manager._bots.items():
        # Only ACSBot instances have _call_connection_id
        if (
            hasattr(bot, "_call_connection_id")
            and bot._call_connection_id == call_connection_id
        ):
            await bot.handle_acs_event(event)
            return

    logger.debug(
        f"ACS event for unknown call_connection_id: {call_connection_id[:20]}... "
        f"(type: {event.get('type', 'unknown')})"
    )


@router.get("/health")
async def acs_health():
    """Health check for ACS callback URL validation."""
    return {"status": "ok", "service": "gneva-acs"}
