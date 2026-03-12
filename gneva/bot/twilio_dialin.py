"""Twilio-based dial-in for Teams meetings.

Flow:
  1. Our backend calls Twilio REST API to dial the Teams number with sendDigits (conference ID)
  2. Twilio connects, enters the DTMF digits, then hits our TwiML webhook
  3. TwiML responds with <Connect><Stream> pointing to our WebSocket bridge
  4. Our WebSocket bridge connects to ElevenLabs ConvAI and pipes audio bidirectionally
  5. ElevenLabs agent is now live in the Teams meeting

Audio format: Both Twilio and ElevenLabs are configured for mulaw 8kHz (ulaw_8000),
so audio passes through without any transcoding.
"""

import asyncio
import json
import logging

import httpx
import websockets
from fastapi import APIRouter, WebSocket, Request
from fastapi.responses import Response
from twilio.rest import Client as TwilioClient

from gneva.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["twilio"])

# Track active sessions: call_sid -> session info
_active_sessions: dict[str, dict] = {}


def make_outbound_call(
    to_number: str,
    conference_id: str,
    meeting_id: str,
) -> dict:
    """Place a Twilio outbound call to a Teams dial-in number with DTMF conference ID.

    Returns dict with call_sid and status.
    """
    settings = get_settings()
    client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)

    # Build DTMF digits: wait 4 seconds (wwwwwwww) then enter conference ID
    # Each 'w' = 0.5s pause. Teams IVR needs time to answer and prompt.
    dtmf_digits = "wwwwwwww" + conference_id
    if not dtmf_digits.endswith("#"):
        dtmf_digits += "#"

    # TwiML webhook URL — Twilio calls this after the call connects and DTMF is sent
    base_url = settings.app_base_url.rstrip("/")
    twiml_url = f"{base_url}/api/twilio/twiml/{meeting_id}"

    call = client.calls.create(
        to=to_number,
        from_=settings.twilio_phone_number,
        url=twiml_url,
        send_digits=dtmf_digits,
        status_callback=f"{base_url}/api/twilio/status",
        status_callback_event=["initiated", "ringing", "answered", "completed"],
        timeout=60,
    )

    # Track this session
    _active_sessions[call.sid] = {
        "meeting_id": meeting_id,
        "call_sid": call.sid,
        "status": "initiated",
    }

    logger.info(f"Twilio call initiated: sid={call.sid} to={to_number} dtmf={conference_id}")

    return {
        "call_sid": call.sid,
        "status": call.status,
    }


@router.post("/api/twilio/twiml/{meeting_id}")
async def twiml_webhook(meeting_id: str, request: Request):
    """TwiML webhook — Twilio calls this after connecting. Returns Stream instruction."""
    from xml.sax.saxutils import escape as xml_escape

    # Sanitize meeting_id to prevent XML injection
    safe_meeting_id = xml_escape(meeting_id, {'"': '&quot;', "'": '&apos;'})

    settings = get_settings()
    base_url = settings.app_base_url.rstrip("/")
    # Convert https to wss for WebSocket URL
    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")
    stream_url = f"{ws_url}/api/twilio/stream/{safe_meeting_id}"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}">
            <Parameter name="meeting_id" value="{safe_meeting_id}" />
        </Stream>
    </Connect>
</Response>"""

    logger.info(f"TwiML response for meeting {meeting_id}: stream -> {stream_url}")
    return Response(content=twiml, media_type="application/xml")


@router.post("/api/twilio/status")
async def status_callback(request: Request):
    """Twilio status callback — track call state changes."""
    form = await request.form()
    call_sid = form.get("CallSid", "")
    status = form.get("CallStatus", "")

    logger.info(f"Twilio status: sid={call_sid} status={status}")

    if call_sid in _active_sessions:
        _active_sessions[call_sid]["status"] = status

    return {"ok": True}


@router.websocket("/api/twilio/stream/{meeting_id}")
async def twilio_stream(ws: WebSocket, meeting_id: str):
    """WebSocket bridge: Twilio media stream <-> ElevenLabs ConvAI agent.

    Both Twilio and ElevenLabs are configured for mulaw 8kHz (ulaw_8000),
    so audio passes straight through without transcoding.
    """
    settings = get_settings()
    await ws.accept()
    logger.info(f"Twilio stream connected for meeting {meeting_id}")

    stream_sid = None
    el_ws = None

    try:
        # Get a signed WebSocket URL from ElevenLabs
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.elevenlabs.io/v1/convai/conversation/get_signed_url?agent_id={settings.elevenlabs_agent_id}",
                headers={"xi-api-key": settings.elevenlabs_api_key},
            )
            resp.raise_for_status()
            signed_url = resp.json()["signed_url"]

        logger.info(f"ElevenLabs signed URL obtained for meeting {meeting_id}")

        # Connect to ElevenLabs ConvAI WebSocket
        el_ws = await websockets.connect(signed_url)

        # Send minimal initialization
        init_msg = {
            "type": "conversation_initiation_client_data",
            "custom_llm_extra_body": {
                "meeting_id": meeting_id,
            },
        }
        await el_ws.send(json.dumps(init_msg))
        logger.info("ElevenLabs init message sent")

        # Bridge audio bidirectionally — no transcoding needed (both use mulaw 8kHz)
        async def twilio_to_elevenlabs():
            """Forward Twilio mulaw audio directly to ElevenLabs."""
            try:
                while True:
                    data = await ws.receive_text()
                    msg = json.loads(data)

                    if msg.get("event") == "start":
                        nonlocal stream_sid
                        stream_sid = msg["start"]["streamSid"]
                        logger.info(f"Twilio stream started: {stream_sid}")

                    elif msg.get("event") == "media":
                        # Pass mulaw audio straight through — no conversion needed
                        if el_ws:
                            await el_ws.send(json.dumps({
                                "user_audio_chunk": msg["media"]["payload"],
                            }))

                    elif msg.get("event") == "stop":
                        logger.info(f"Twilio stream stopped: {stream_sid}")
                        break

            except Exception as e:
                logger.error(f"Twilio->ElevenLabs error: {e}")

        async def elevenlabs_to_twilio():
            """Forward ElevenLabs mulaw audio directly back to Twilio."""
            try:
                async for message in el_ws:
                    msg = json.loads(message)
                    msg_type = msg.get("type", "")

                    if msg_type == "audio":
                        # Two possible audio payload locations
                        audio_data = None
                        if msg.get("audio", {}).get("chunk"):
                            audio_data = msg["audio"]["chunk"]
                        elif msg.get("audio_event", {}).get("audio_base_64"):
                            audio_data = msg["audio_event"]["audio_base_64"]

                        # Pass mulaw audio straight through — no conversion needed
                        if audio_data and stream_sid:
                            await ws.send_json({
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": audio_data,
                                },
                            })

                    elif msg_type == "interruption":
                        # User started speaking — clear Twilio's audio buffer
                        if stream_sid:
                            await ws.send_json({
                                "event": "clear",
                                "streamSid": stream_sid,
                            })

                    elif msg_type == "ping":
                        # Must respond with pong including the event_id
                        event_id = msg.get("ping_event", {}).get("event_id") or msg.get("event_id")
                        pong = {"type": "pong"}
                        if event_id:
                            pong["event_id"] = event_id
                        await el_ws.send(json.dumps(pong))

                    elif msg_type == "agent_response":
                        text = msg.get("agent_response_correction", {}).get("corrected", "") or msg.get("agent_response", "")
                        if text:
                            logger.info(f"Agent said: {text[:100]}")

                    elif msg_type == "user_transcript":
                        text = msg.get("user_transcription_event", {}).get("user_transcript", "")
                        if text:
                            logger.info(f"User said: {text[:100]}")

                    elif msg_type == "conversation_initiation_metadata":
                        conv_id = msg.get("conversation_initiation_metadata_event", {}).get("conversation_id", "")
                        logger.info(f"ElevenLabs conversation started: {conv_id}")

            except Exception as e:
                logger.error(f"ElevenLabs->Twilio error: {e}")

        # Run both directions concurrently
        await asyncio.gather(
            twilio_to_elevenlabs(),
            elevenlabs_to_twilio(),
        )

    except Exception as e:
        logger.error(f"Stream bridge error for meeting {meeting_id}: {e}")
    finally:
        if el_ws:
            await el_ws.close()
        logger.info(f"Stream bridge closed for meeting {meeting_id}")
