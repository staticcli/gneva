"""ACSBot — meeting bot using Azure Communication Services Call Automation.

Replaces the browser-based BrowserBot with a proper ACS-based bot that:
- Joins Teams meetings via ACS Call Automation SDK
- Receives per-speaker unmixed audio via bidirectional WebSocket
- Sends TTS audio back into the meeting via the WebSocket
- No browser required — pure server-side integration
"""

import asyncio
import base64
import json
import logging
import os
import struct
import uuid
import wave
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import websockets

logger = logging.getLogger(__name__)

# Re-use BotState from browser_bot for consistency
from gneva.bot.browser_bot import BotState


class ACSBot:
    """A meeting bot that joins via Azure Communication Services Call Automation.

    Provides the same interface as BrowserBot so it can be used as a drop-in
    replacement via BotManager.
    """

    def __init__(
        self,
        meeting_url: str,
        bot_name: str = "Gneva",
        consent_message: str = "Gneva AI is recording this meeting for notes and action items.",
        audio_dir: str = "/tmp/gneva/audio",
        lobby_timeout: int = 300,
        max_duration: int = 14400,
        meeting_id: str | None = None,
        on_complete=None,
        voice_id: str | None = None,
        org_id: str | None = None,
        greeting_mode: str = "personalized",
    ):
        self.bot_id = str(uuid.uuid4())
        self.meeting_url = meeting_url
        self.bot_name = bot_name
        self.consent_message = consent_message
        self.audio_dir = audio_dir
        self.lobby_timeout = lobby_timeout
        self.max_duration = max_duration
        self.meeting_id = meeting_id
        self.on_complete = on_complete
        self.voice_id = voice_id
        self.org_id = org_id
        self.greeting_mode = greeting_mode
        self.on_state_change = None  # async callback(bot_id, meeting_id, new_state)

        self._state = BotState.INITIALIZING
        self.status_message: str = "Initializing..."
        self.platform = "teams"  # ACS only supports Teams meetings
        self.error: str | None = None
        self.started_at: datetime | None = None
        self.ended_at: datetime | None = None
        self.audio_path: str | None = None

        # ACS resources
        self._acs_client = None
        self._call_connection = None
        self._call_connection_id: str | None = None

        # Audio streaming
        self._ws_server = None
        self._ws_connection = None  # The WebSocket connection from ACS
        self._ws_port: int = 0
        self._audio_ws_ready = asyncio.Event()

        # STT and conversation
        self._realtime_stt = None
        self._conversation = None
        self._stop_event = asyncio.Event()

        # Participant tracking: ACS raw ID -> display name
        self._participants: dict[str, str] = {}
        # Track ID (from unmixed audio) -> participant raw ID
        self._track_to_participant: dict[int, str] = {}

        # Audio recording buffer (collect all audio for pipeline)
        self._audio_buffer = bytearray()
        self._total_audio_bytes = 0

        # Event handling
        self._event_queue: asyncio.Queue = asyncio.Queue()

    @property
    def state(self) -> BotState:
        return self._state

    @state.setter
    def state(self, new_state: BotState):
        old = self._state
        self._state = new_state
        if old != new_state and self.on_state_change and self.meeting_id:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.on_state_change(
                        self.bot_id, self.meeting_id, new_state.value
                    ))
            except Exception:
                pass

    async def run(self, _playwright=None):
        """Main lifecycle: connect ACS -> join meeting -> stream audio -> leave.

        The _playwright parameter is accepted for interface compatibility with
        BrowserBot but is ignored — ACS doesn't need a browser.
        """
        try:
            self.started_at = datetime.utcnow()
            await self._setup_acs_client()
            await self._start_ws_server()
            await self._join_meeting()

            if self.state == BotState.FAILED:
                return

            await self._start_recording()
            await self._monitor_meeting()
            await self._leave_meeting()
        except asyncio.CancelledError:
            logger.info(f"ACSBot {self.bot_id} cancelled — saving transcript")
            await self._emergency_save()
            self.state = BotState.ENDED
        except Exception as e:
            logger.error(f"ACSBot {self.bot_id} error: {e}", exc_info=True)
            await self._emergency_save()
            self.state = BotState.FAILED
            self.error = str(e)
        finally:
            await self._cleanup()

    async def stop(self):
        """Signal the bot to leave and stop."""
        self._stop_event.set()

    async def leave(self):
        """Leave the meeting (alias for stop, for interface compatibility)."""
        await self.stop()

    async def speak(self, text: str):
        """Synthesize speech via TTS and send it into the meeting via WebSocket.

        For ACS, we can either:
        1. Use the Play action via Call Automation SDK (server-side)
        2. Send raw audio through the bidirectional WebSocket

        We use approach 2 (WebSocket) for lower latency and to avoid needing
        a publicly hosted audio file URL.
        """
        if self.state not in (BotState.IN_MEETING, BotState.RECORDING):
            logger.warning(f"ACSBot {self.bot_id}: cannot speak — not in meeting")
            return

        try:
            from gneva.services.tts import TTSService, EDGE_TTS_VOICES
            tts = TTSService()
            if self.voice_id:
                tts._el_voice = self.voice_id
                try:
                    from gneva.bot.talking_head import VOICE_FACE_MAP
                    face_name = VOICE_FACE_MAP.get(self.voice_id, "").replace(".jpg", "")
                    if face_name in EDGE_TTS_VOICES:
                        tts._edge_voice = EDGE_TTS_VOICES[face_name]
                except Exception:
                    pass

            audio_bytes = await tts.synthesize(text)

            # Convert WAV to raw PCM16 mono 16kHz for ACS audio streaming
            pcm_data = self._wav_to_pcm16_16khz(audio_bytes)

            if self._ws_connection:
                await self._send_audio_to_meeting(pcm_data)
                duration = len(pcm_data) / (16000 * 2)  # 16kHz, 16-bit
                await asyncio.sleep(duration + 0.3)
                logger.info(f"ACSBot {self.bot_id}: spoke for {duration:.1f}s — '{text[:50]}...'")
            elif self._call_connection:
                # Fallback: use ACS Play action with SSML
                await self._play_via_acs(text)
            else:
                logger.warning(f"ACSBot {self.bot_id}: no audio channel available for speak()")

        except Exception as e:
            logger.error(f"ACSBot {self.bot_id}: speak error: {e}", exc_info=True)

    async def speak_streaming(self, text: str):
        """Speak text with sentence-level streaming for faster first-word latency."""
        if self.state not in (BotState.IN_MEETING, BotState.RECORDING):
            return

        import re
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 2]

        if not sentences:
            return

        if len(sentences) <= 2 and len(text) < 100:
            await self.speak(text)
            return

        for sentence in sentences:
            await self.speak(sentence)

    def to_dict(self) -> dict:
        """Return bot status as a dict."""
        duration = 0.0
        if self._total_audio_bytes > 0:
            duration = self._total_audio_bytes / (16000 * 2)

        return {
            "bot_id": self.bot_id,
            "meeting_id": self.meeting_id,
            "state": self.state.value,
            "status_message": self.status_message,
            "platform": self.platform,
            "bot_name": self.bot_name,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "audio_path": self.audio_path,
            "duration_sec": round(duration, 1),
        }

    # ── ACS Setup ──────────────────────────────────────────────────────

    async def _setup_acs_client(self):
        """Initialize the ACS Call Automation client."""
        from gneva.config import get_settings
        settings = get_settings()

        if not settings.acs_connection_string:
            raise RuntimeError(
                "ACS connection string not configured. "
                "Set ACS_CONNECTION_STRING in your environment."
            )

        from azure.communication.callautomation import CallAutomationClient

        self._acs_client = CallAutomationClient.from_connection_string(
            settings.acs_connection_string
        )
        logger.info(f"ACSBot {self.bot_id}: ACS client initialized")

    async def _start_ws_server(self):
        """Start a local WebSocket server for ACS audio streaming.

        ACS connects TO this server (outbound from Azure). For production,
        this URL must be publicly accessible (via ngrok, load balancer, etc.).
        The URL is configured via acs_ws_url in settings.
        """
        from gneva.config import get_settings
        settings = get_settings()

        # Find a free port for the WebSocket server
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("0.0.0.0", 0))
        self._ws_port = sock.getsockname()[1]
        sock.close()

        self._ws_server = await websockets.serve(
            self._handle_audio_ws,
            "0.0.0.0",
            self._ws_port,
        )
        logger.info(f"ACSBot {self.bot_id}: audio WebSocket server on port {self._ws_port}")

    async def _handle_audio_ws(self, websocket, path=None):
        """Handle the bidirectional audio WebSocket connection from ACS.

        ACS sends JSON messages with audio data in base64. Each message includes:
        - kind: "AudioData" for audio chunks
        - audioData: base64-encoded PCM16 audio
        - participantRawId: speaker identifier (unmixed mode)
        - timestamp: server timestamp
        - silent: whether the chunk is silence
        """
        logger.info(f"ACSBot {self.bot_id}: audio WebSocket connected")
        self._ws_connection = websocket
        self._audio_ws_ready.set()

        try:
            async for raw_message in websocket:
                if self._stop_event.is_set():
                    break

                try:
                    msg = json.loads(raw_message)
                except (json.JSONDecodeError, TypeError):
                    # Binary frame — treat as raw PCM audio
                    if isinstance(raw_message, bytes):
                        self._process_raw_audio(raw_message, track_id=0)
                    continue

                kind = msg.get("kind", "")

                if kind == "AudioData":
                    await self._process_audio_message(msg)
                elif kind == "AudioMetadata":
                    # Audio stream metadata (encoding, sample rate, etc.)
                    logger.info(
                        f"ACSBot {self.bot_id}: audio metadata — "
                        f"encoding={msg.get('encoding')}, "
                        f"sampleRate={msg.get('sampleRate')}, "
                        f"channels={msg.get('channels')}"
                    )
                elif kind == "StopAudio":
                    logger.info(f"ACSBot {self.bot_id}: audio stream stopped by ACS")
                else:
                    logger.debug(f"ACSBot {self.bot_id}: unknown WS message kind: {kind}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"ACSBot {self.bot_id}: audio WebSocket disconnected")
        except Exception as e:
            logger.error(f"ACSBot {self.bot_id}: audio WS error: {e}", exc_info=True)
        finally:
            self._ws_connection = None

    async def _process_audio_message(self, msg: dict):
        """Process an AudioData message from ACS.

        In unmixed mode, each message has a participantRawId identifying
        the speaker, so we can feed per-speaker audio to STT.
        """
        audio_b64 = msg.get("audioData", {}).get("data", "")
        if not audio_b64:
            # Try alternate payload shapes
            audio_b64 = msg.get("data", "")

        if not audio_b64:
            return

        is_silent = msg.get("audioData", {}).get("silent", False)
        participant_id = msg.get("audioData", {}).get("participantRawId", "")

        pcm_bytes = base64.b64decode(audio_b64)

        # Map participant to a numeric track ID for STT
        if participant_id:
            track_id = self._get_track_id(participant_id)
        else:
            track_id = 0

        self._process_raw_audio(pcm_bytes, track_id, is_silent)

    def _process_raw_audio(self, pcm_bytes: bytes, track_id: int = 0, is_silent: bool = False):
        """Feed raw PCM audio to STT and recording buffer."""
        # Accumulate for recording
        self._audio_buffer.extend(pcm_bytes)
        self._total_audio_bytes += len(pcm_bytes)

        # Feed to STT (skip silent chunks to reduce CPU)
        if not is_silent and self._realtime_stt:
            self._realtime_stt.feed_audio(pcm_bytes, track_id)

    def _get_track_id(self, participant_raw_id: str) -> int:
        """Map a participant raw ID to a numeric track ID.

        Uses a stable hash so the same participant always gets the same track.
        """
        # Check existing mapping
        for tid, pid in self._track_to_participant.items():
            if pid == participant_raw_id:
                return tid

        # Assign new track ID (1-based; 0 is reserved for mixed/unknown)
        track_id = len(self._track_to_participant) + 1
        self._track_to_participant[track_id] = participant_raw_id

        # Try to resolve display name
        display_name = self._participants.get(participant_raw_id, "")
        if display_name:
            logger.info(
                f"ACSBot {self.bot_id}: mapped track {track_id} -> "
                f"'{display_name}' ({participant_raw_id[:20]}...)"
            )

        return track_id

    # ── Meeting Join / Leave ───────────────────────────────────────────

    async def _join_meeting(self):
        """Join the Teams meeting via ACS Call Automation REST API.

        Uses the /calling/callConnections:connect endpoint with a teamsMeetingLink
        call locator to join an existing Teams meeting. This bypasses the SDK's
        create_call() which doesn't support Teams meeting links natively.
        """
        self.state = BotState.JOINING
        self.status_message = "Connecting to Teams meeting via ACS..."

        from gneva.config import get_settings
        settings = get_settings()

        try:
            from azure.communication.callautomation import (
                MediaStreamingOptions,
                StreamingTransportType,
                MediaStreamingContentType,
                MediaStreamingAudioChannelType,
            )

            # Build the transport URL for audio streaming
            ws_url = settings.acs_ws_url
            if not ws_url:
                ws_url = f"wss://localhost:{self._ws_port}"
                logger.warning(
                    f"ACSBot {self.bot_id}: acs_ws_url not set — using {ws_url}. "
                    "This only works if ACS can reach this host."
                )

            # Build the callback URL for ACS events
            callback_url = settings.acs_callback_url
            if not callback_url:
                callback_url = "https://localhost:8100/api/acs/events"
                logger.warning(
                    f"ACSBot {self.bot_id}: acs_callback_url not set — using {callback_url}. "
                    "This only works if ACS can reach this host."
                )

            media_streaming = MediaStreamingOptions(
                transport_url=ws_url,
                transport_type=StreamingTransportType.WEBSOCKET,
                content_type=MediaStreamingContentType.AUDIO,
                audio_channel_type=MediaStreamingAudioChannelType.UNMIXED,
            )
            media_config = media_streaming._to_generated()  # pylint: disable=protected-access

            # Use the connect endpoint which accepts a callLocator
            # (no targets required, unlike createCall)
            request_body = {
                "callLocator": {
                    "teamsMeetingLink": self.meeting_url,
                    "kind": "teamsMeetingLink",
                },
                "callbackUri": callback_url,
                "sourceDisplayName": self.bot_name,
                "mediaStreamingOptions": {
                    "transportUrl": media_config.transport_url,
                    "transportType": media_config.transport_type.value
                        if hasattr(media_config.transport_type, "value")
                        else str(media_config.transport_type),
                    "contentType": media_config.content_type.value
                        if hasattr(media_config.content_type, "value")
                        else str(media_config.content_type),
                    "audioChannelType": media_config.audio_channel_type.value
                        if hasattr(media_config.audio_channel_type, "value")
                        else str(media_config.audio_channel_type),
                },
            }

            from azure.core.rest import HttpRequest as AzureHttpRequest
            api_version = self._acs_client._client._config.api_version
            endpoint = self._acs_client._client._config.endpoint.rstrip("/")
            full_url = f"{endpoint}/calling/callConnections:connect?api-version={api_version}"

            logger.info(
                f"ACSBot {self.bot_id}: connecting to Teams meeting via {full_url}"
            )
            logger.info(
                f"ACSBot {self.bot_id}: callback={callback_url}, ws={ws_url}"
            )

            http_request = AzureHttpRequest(
                method="POST",
                url=full_url,
                json=request_body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )

            response = await asyncio.to_thread(
                self._acs_client._client._client.send_request,
                http_request,
            )

            if response.status_code not in (200, 201):
                error_body = response.text()
                raise RuntimeError(
                    f"ACS connect failed: HTTP {response.status_code} — {error_body}"
                )

            result = response.json()
            self._call_connection_id = result.get("callConnectionId", "")

            # Get a CallConnection object for later operations (hang up, play, etc.)
            if self._call_connection_id:
                self._call_connection = self._acs_client.get_call_connection(
                    self._call_connection_id
                )

            logger.info(
                f"ACSBot {self.bot_id}: call initiated, "
                f"connection_id={self._call_connection_id}"
            )

            # Wait for the call to connect (CallConnected event via webhook)
            self.status_message = "Waiting for Teams meeting to accept..."
            connected = await self._wait_for_event("CallConnected", timeout=self.lobby_timeout)

            if not connected:
                self.state = BotState.FAILED
                self.status_message = "Timed out waiting for meeting to accept"
                self.error = "Meeting connection timeout"
                return

            self.state = BotState.IN_MEETING
            self.status_message = "Connected to meeting — starting conversation engine..."

            # Start conversation engine
            try:
                from gneva.bot.conversation import ConversationEngine
                self._conversation = ConversationEngine(
                    bot=self,
                    org_id=str(self.org_id) if self.org_id else None,
                    greeting_mode=self.greeting_mode,
                )
                await self._conversation.start()
                self.status_message = "Delivering greeting..."
                await self._conversation.greet()
                logger.info(f"ACSBot {self.bot_id}: conversation engine started")
            except Exception as e:
                logger.warning(f"ACSBot {self.bot_id}: conversation engine failed: {e}")

            self.status_message = "Active — listening and recording"
            logger.info(f"ACSBot {self.bot_id}: in meeting")

        except ImportError as e:
            self.state = BotState.FAILED
            self.error = f"ACS SDK not installed: {e}"
            self.status_message = "ACS SDK not installed"
            logger.error(
                f"ACSBot {self.bot_id}: azure-communication-callautomation not installed. "
                f"Install with: pip install azure-communication-callautomation"
            )
        except Exception as e:
            self.state = BotState.FAILED
            self.error = str(e)
            self.status_message = f"Failed to join: {e}"
            logger.error(f"ACSBot {self.bot_id}: join failed: {e}", exc_info=True)

    async def _start_recording(self):
        """Start real-time STT on the incoming audio streams."""
        os.makedirs(self.audio_dir, exist_ok=True)

        if self._conversation:
            try:
                from gneva.bot.realtime_stt import RealtimeSTT
                from gneva.config import get_settings
                settings = get_settings()

                self._realtime_stt = RealtimeSTT(
                    on_utterance=self._on_stt_utterance,
                    backend=settings.stt_backend,
                    model_size=settings.stt_model_size,
                )
                await self._realtime_stt.start()
                logger.info(
                    f"ACSBot {self.bot_id}: real-time STT started "
                    f"({settings.stt_backend}/{settings.stt_model_size})"
                )
            except Exception as e:
                logger.warning(f"ACSBot {self.bot_id}: STT init failed: {e}")
                self._realtime_stt = None

        self.state = BotState.RECORDING
        self.status_message = "Recording — per-speaker audio via ACS"

    async def _monitor_meeting(self):
        """Monitor the meeting for end signals, timeouts, and participant updates."""
        deadline = datetime.utcnow() + timedelta(seconds=self.max_duration)
        last_log_time = datetime.utcnow()
        poll_count = 0

        while not self._stop_event.is_set():
            poll_count += 1

            # Process any pending ACS events
            while not self._event_queue.empty():
                try:
                    event = self._event_queue.get_nowait()
                    await self._handle_acs_event(event)
                except asyncio.QueueEmpty:
                    break

            # Check max duration
            if datetime.utcnow() > deadline:
                logger.info(f"ACSBot {self.bot_id}: max duration reached")
                break

            # Check if the WebSocket connection is gone (meeting ended)
            if (
                self._audio_ws_ready.is_set()
                and self._ws_connection is None
                and self.state == BotState.RECORDING
            ):
                # WS was connected but now it's gone
                logger.info(f"ACSBot {self.bot_id}: audio WebSocket lost — meeting may have ended")
                # Wait a moment for reconnection
                await asyncio.sleep(5)
                if self._ws_connection is None:
                    logger.info(f"ACSBot {self.bot_id}: confirmed — meeting ended")
                    break

            # Periodic logging
            now = datetime.utcnow()
            if (now - last_log_time).total_seconds() >= 60:
                duration = self._total_audio_bytes / (16000 * 2) if self._total_audio_bytes > 0 else 0
                logger.info(
                    f"ACSBot {self.bot_id}: monitoring — state={self.state.value}, "
                    f"polls={poll_count}, audio={duration:.1f}s, "
                    f"participants={len(self._participants)}"
                )
                last_log_time = now

            await asyncio.sleep(0.5)

    async def _leave_meeting(self):
        """Leave the meeting and finalize recordings."""
        self.state = BotState.LEAVING
        self.status_message = "Leaving meeting..."

        # Stop conversation engine
        if self._conversation:
            try:
                await self._conversation.stop()
            except Exception:
                pass

        # Hang up via ACS
        if self._call_connection:
            try:
                await asyncio.to_thread(self._call_connection.hang_up, is_for_everyone=False)
                logger.info(f"ACSBot {self.bot_id}: hung up via ACS")
            except Exception as e:
                logger.warning(f"ACSBot {self.bot_id}: hang up error: {e}")

        # Save audio recording
        await self._save_audio()

        # Save caption transcript from conversation engine
        has_captions = False
        if self._conversation and self._conversation._transcript_buffer:
            caption_segments = [
                {"speaker": s.get("speaker", "Unknown"), "text": s.get("text", ""), "ts": 0}
                for s in self._conversation._transcript_buffer
                if s.get("text", "").strip()
            ]
            if caption_segments and self.meeting_id:
                try:
                    await self._save_caption_transcript(caption_segments)
                    has_captions = True
                except Exception as e:
                    logger.error(f"ACSBot {self.bot_id}: transcript save failed: {e}")

        self.ended_at = datetime.utcnow()
        self.state = BotState.ENDED

        has_audio = self._total_audio_bytes > 0
        success = has_audio or has_captions
        logger.info(
            f"ACSBot {self.bot_id}: meeting ended — "
            f"audio={'yes' if has_audio else 'no'}, "
            f"captions={'yes' if has_captions else 'no'}, "
            f"success={success}"
        )

        if self.on_complete:
            try:
                await self.on_complete(
                    bot_id=self.bot_id,
                    meeting_id=self.meeting_id,
                    audio_path=self.audio_path,
                    success=success,
                )
            except Exception as e:
                logger.error(f"ACSBot {self.bot_id}: on_complete error: {e}")

    async def _emergency_save(self):
        """Save whatever we have when unexpectedly disconnected."""
        try:
            if self._conversation:
                try:
                    await self._conversation.stop()
                except Exception:
                    pass

                if self._conversation._transcript_buffer and self.meeting_id:
                    caption_segments = [
                        {"speaker": s.get("speaker", "Unknown"), "text": s.get("text", ""), "ts": 0}
                        for s in self._conversation._transcript_buffer
                        if s.get("text", "").strip()
                    ]
                    if caption_segments:
                        try:
                            await self._save_caption_transcript(caption_segments)
                        except Exception as e:
                            logger.warning(f"ACSBot {self.bot_id}: emergency transcript save failed: {e}")

            await self._save_audio()

            self.ended_at = datetime.utcnow()
            if self.on_complete and self.meeting_id:
                try:
                    await self.on_complete(
                        bot_id=self.bot_id,
                        meeting_id=self.meeting_id,
                        audio_path=self.audio_path,
                        success=True,
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"ACSBot {self.bot_id}: emergency save failed: {e}")

    # ── Audio I/O ──────────────────────────────────────────────────────

    async def _send_audio_to_meeting(self, pcm_data: bytes):
        """Send PCM16 16kHz audio back to the meeting via WebSocket.

        ACS expects audio data as base64-encoded PCM in a JSON message:
        {
            "kind": "AudioData",
            "audioData": {
                "data": "<base64>",
                "timestamp": "2024-...",
                "participantRawId": null,
                "silent": false
            }
        }
        """
        if not self._ws_connection:
            return

        # Send in chunks to avoid overwhelming the WebSocket
        chunk_size = 16000 * 2 // 10  # 100ms chunks at 16kHz 16-bit
        offset = 0

        while offset < len(pcm_data):
            chunk = pcm_data[offset:offset + chunk_size]
            msg = {
                "kind": "AudioData",
                "audioData": {
                    "data": base64.b64encode(chunk).decode(),
                    "silent": False,
                },
            }
            try:
                await self._ws_connection.send(json.dumps(msg))
            except Exception as e:
                logger.warning(f"ACSBot {self.bot_id}: failed to send audio chunk: {e}")
                break
            offset += chunk_size
            # Small delay between chunks to maintain real-time pacing
            await asyncio.sleep(0.09)  # ~100ms per chunk

    async def _play_via_acs(self, text: str):
        """Fallback: use ACS Play action with SSML for TTS.

        This uses Azure's built-in TTS via the Call Automation Play API.
        Less control than our own TTS, but doesn't require WebSocket audio.
        """
        if not self._call_connection:
            return

        try:
            from azure.communication.callautomation import (
                SsmlSource,
            )

            # Use Azure Neural TTS via SSML
            ssml = (
                f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">'
                f'<voice name="en-US-JennyNeural">{text}</voice>'
                f'</speak>'
            )

            ssml_source = SsmlSource(ssml_text=ssml)
            await asyncio.to_thread(
                self._call_connection.play_media,
                play_source=ssml_source,
            )
            logger.info(f"ACSBot {self.bot_id}: played via ACS SSML — '{text[:50]}...'")
            # Estimate duration (rough: ~150ms per word)
            word_count = len(text.split())
            await asyncio.sleep(word_count * 0.15 + 1.0)

        except Exception as e:
            logger.error(f"ACSBot {self.bot_id}: ACS Play failed: {e}")

    def _wav_to_pcm16_16khz(self, wav_bytes: bytes) -> bytes:
        """Convert WAV audio to raw PCM16 mono 16kHz.

        Our TTS engines produce WAV files that may have different sample rates.
        ACS audio streaming requires 16kHz 16-bit mono PCM.
        """
        import io

        try:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                frame_rate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())

            import numpy as np

            # Convert to numpy array
            if sample_width == 2:
                dtype = np.int16
            elif sample_width == 4:
                dtype = np.int32
            elif sample_width == 1:
                dtype = np.uint8
            else:
                raise ValueError(f"Unsupported sample width: {sample_width}")

            samples = np.frombuffer(frames, dtype=dtype)

            # Convert to float32 for processing
            if dtype == np.int16:
                samples = samples.astype(np.float32) / 32768.0
            elif dtype == np.int32:
                samples = samples.astype(np.float32) / 2147483648.0
            elif dtype == np.uint8:
                samples = (samples.astype(np.float32) - 128.0) / 128.0

            # Convert stereo to mono
            if channels > 1:
                samples = samples.reshape(-1, channels).mean(axis=1)

            # Resample to 16kHz if needed
            if frame_rate != 16000:
                num_samples = int(len(samples) * 16000 / frame_rate)
                indices = np.linspace(0, len(samples) - 1, num_samples)
                samples = np.interp(indices, np.arange(len(samples)), samples)

            # Convert back to int16
            pcm16 = (samples * 32767).astype(np.int16)
            return pcm16.tobytes()

        except Exception as e:
            logger.error(f"ACSBot {self.bot_id}: WAV conversion error: {e}")
            # Return the raw bytes as-is and hope for the best
            return wav_bytes

    async def _save_audio(self):
        """Save the accumulated audio buffer to a WAV file."""
        if not self._audio_buffer:
            return

        audio_file = os.path.join(self.audio_dir, f"{self.bot_id}.wav")
        os.makedirs(self.audio_dir, exist_ok=True)

        try:
            with wave.open(audio_file, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(16000)
                wf.writeframes(bytes(self._audio_buffer))

            self.audio_path = audio_file
            duration = len(self._audio_buffer) / (16000 * 2)
            logger.info(f"ACSBot {self.bot_id}: audio saved ({duration:.1f}s) to {audio_file}")
        except Exception as e:
            logger.error(f"ACSBot {self.bot_id}: audio save failed: {e}")

    # ── ACS Event Handling ─────────────────────────────────────────────

    async def handle_acs_event(self, event_data: dict):
        """Public method to receive ACS webhook events from the FastAPI endpoint.

        Called by the /api/acs/events endpoint when ACS sends callback events.
        """
        await self._event_queue.put(event_data)

    async def _handle_acs_event(self, event: dict):
        """Process an ACS Call Automation event."""
        event_type = event.get("type", "")

        if "CallConnected" in event_type:
            logger.info(f"ACSBot {self.bot_id}: CallConnected event received")
            self._call_connected_event.set()

        elif "ParticipantsUpdated" in event_type:
            participants = event.get("data", {}).get("participants", [])
            for p in participants:
                raw_id = p.get("identifier", {}).get("rawId", "")
                display_name = p.get("displayName", "")
                if raw_id and display_name:
                    self._participants[raw_id] = display_name
                    logger.debug(
                        f"ACSBot {self.bot_id}: participant update — "
                        f"'{display_name}' ({raw_id[:20]}...)"
                    )

        elif "CallDisconnected" in event_type:
            logger.info(f"ACSBot {self.bot_id}: CallDisconnected — meeting ended")
            self._stop_event.set()

        elif "PlayCompleted" in event_type:
            logger.debug(f"ACSBot {self.bot_id}: PlayCompleted")

        elif "PlayFailed" in event_type:
            reason = event.get("data", {}).get("resultInformation", {}).get("message", "unknown")
            logger.warning(f"ACSBot {self.bot_id}: PlayFailed — {reason}")

        else:
            logger.debug(f"ACSBot {self.bot_id}: unhandled event — {event_type}")

    async def _wait_for_event(self, event_name: str, timeout: int = 300) -> bool:
        """Wait for a specific ACS event to arrive."""
        self._call_connected_event = asyncio.Event()

        if event_name == "CallConnected":
            try:
                await asyncio.wait_for(self._call_connected_event.wait(), timeout=timeout)
                return True
            except asyncio.TimeoutError:
                return False

        return False

    # ── STT Callback ───────────────────────────────────────────────────

    async def _on_stt_utterance(self, text: str, confidence: float, track_id: int = 0):
        """Callback from RealtimeSTT when a complete utterance is transcribed.

        Uses the track_id to look up the participant name from ACS participant data.
        """
        if not self._conversation or not text.strip():
            return

        # Resolve speaker name from track -> participant mapping
        speaker = "Participant"
        if track_id in self._track_to_participant:
            participant_id = self._track_to_participant[track_id]
            speaker = self._participants.get(participant_id, "Participant")

        logger.debug(
            f"ACSBot {self.bot_id}: STT utterance (track={track_id}, conf={confidence:.2f}): "
            f"[{speaker}] '{text[:80]}'"
        )
        await self._conversation.on_transcript_segment(text, speaker)

    # ── Transcript Persistence ─────────────────────────────────────────

    async def _save_caption_transcript(self, caption_segments: list):
        """Save transcript segments to the database (same as BrowserBot)."""
        import uuid as uuid_mod
        from gneva.db import async_session_factory
        from gneva.models.meeting import Transcript, TranscriptSegment

        meeting_uuid = uuid_mod.UUID(self.meeting_id)

        full_text_parts = []
        for seg in caption_segments:
            speaker = seg.get("speaker", "Participant")
            text = seg.get("text", "")
            if text.strip():
                full_text_parts.append(f"{speaker}: {text}")

        full_text = "\n".join(full_text_parts)
        if not full_text.strip():
            return

        async with async_session_factory() as db:
            transcript = Transcript(
                meeting_id=meeting_uuid,
                version=1,
                full_text=full_text,
                word_count=len(full_text.split()),
                language="en",
            )
            db.add(transcript)
            await db.flush()

            for i, seg in enumerate(caption_segments):
                text = seg.get("text", "").strip()
                if not text:
                    continue
                speaker = seg.get("speaker", "Participant")
                ts = seg.get("ts", 0)
                first_ts = caption_segments[0].get("ts", 0) if caption_segments else 0
                offset_ms = int(ts - first_ts) if ts and first_ts else i * 3000

                db.add(TranscriptSegment(
                    transcript_id=transcript.id,
                    speaker_label=speaker,
                    start_ms=offset_ms,
                    end_ms=offset_ms + 3000,
                    text=text,
                    confidence=0.90,  # ACS per-speaker audio is higher quality than caption scraping
                ))

            await db.commit()
            logger.info(
                f"ACSBot {self.bot_id}: saved transcript — "
                f"{len(caption_segments)} segments, {len(full_text)} chars"
            )

    # ── Cleanup ────────────────────────────────────────────────────────

    async def _cleanup(self):
        """Release all resources."""
        try:
            if self._realtime_stt:
                await self._realtime_stt.stop()
        except Exception:
            pass

        try:
            if self._ws_server:
                self._ws_server.close()
                await self._ws_server.wait_closed()
        except Exception:
            pass

        try:
            if self._ws_connection:
                await self._ws_connection.close()
        except Exception:
            pass

        logger.info(f"ACSBot {self.bot_id}: cleaned up")
