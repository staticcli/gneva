"""ACSCallingBot — joins Teams meetings via ACS Calling SDK in a headless browser.

Instead of navigating to the Teams web client and scraping captions, this bot:
1. Opens a local HTML page with the ACS Calling SDK bundled
2. Gets a VOIP token from ACS Identity service
3. Joins the Teams meeting via the SDK's callAgent.join()
4. Receives real audio streams from remote participants (per-speaker)
5. Sends TTS audio back into the call via LocalAudioStream

Same interface as BrowserBot — drop-in replacement.
"""

import asyncio
import uuid
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

import http.server
import threading

from gneva.bot.audio_capture import AudioCapture
from gneva.bot.browser_bot import BotState

logger = logging.getLogger(__name__)

# Path to the ACS calling HTML page + bundle
ACS_CALLING_DIR = Path(__file__).parent / "acs_calling"
ACS_HTML_PATH = ACS_CALLING_DIR / "acs_meeting.html"


class _ACSHandler(http.server.SimpleHTTPRequestHandler):
    """Static file handler for the ACS calling page."""

    def log_message(self, format, *args):
        # Suppress HTTP request logging
        pass


class _StaticServer:
    """Tiny HTTP server to serve the ACS calling page and JS bundle."""

    def __init__(self, directory: str):
        self.directory = directory
        self._server = None
        self._thread = None
        self.port = 0

    def start(self):
        _ACSHandler.directory = self.directory  # Class-level attribute
        # Use functools.partial to bind directory
        import functools
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=self.directory)
        self._server = http.server.HTTPServer(("127.0.0.1", 0), handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info(f"Static server started on port {self.port} serving {self.directory}")

    def stop(self):
        if self._server:
            self._server.shutdown()

    def url(self, path: str = "") -> str:
        return f"http://127.0.0.1:{self.port}/{path}"


class ACSCallingBot:
    """A meeting bot that joins via ACS Calling SDK running in a Playwright browser."""

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
        self.on_state_change = None

        self._state = BotState.INITIALIZING
        self.status_message: str = "Initializing..."
        self.platform = "teams"
        self.error: str | None = None
        self.started_at: datetime | None = None
        self.ended_at: datetime | None = None
        self.audio_path: str | None = None

        self._browser = None
        self._context = None
        self._page = None
        self._audio_capture: AudioCapture | None = None
        self._realtime_stt = None
        self._conversation = None
        self._stop_event = asyncio.Event()

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

    async def run(self, playwright):
        """Main lifecycle: launch browser → join via ACS SDK → record → leave."""
        try:
            self.started_at = datetime.utcnow()
            await self._launch_browser(playwright)
            await self._join_meeting()

            if self.state == BotState.FAILED:
                return

            await self._start_recording()
            await self._monitor_meeting()
            await self._leave_meeting()
        except asyncio.CancelledError:
            logger.info(f"ACSCallingBot {self.bot_id} cancelled")
            await self._emergency_save()
            self.state = BotState.ENDED
        except Exception as e:
            logger.error(f"ACSCallingBot {self.bot_id} error: {e}", exc_info=True)
            await self._emergency_save()
            self.state = BotState.FAILED
            self.error = str(e)
        finally:
            await self._cleanup()

    async def stop(self):
        self._stop_event.set()

    async def leave(self):
        await self.stop()

    async def speak(self, text: str):
        """Send TTS audio into the meeting via WebSocket → ACS LocalAudioStream."""
        if self.state not in (BotState.IN_MEETING, BotState.RECORDING):
            return

        try:
            from gneva.services.tts import TTSService
            tts = TTSService()
            if self.voice_id:
                tts._el_voice = self.voice_id

            audio_bytes = await tts.synthesize(text)

            # Convert WAV to raw PCM16 16kHz
            pcm_data = self._wav_to_pcm16(audio_bytes)

            # Send PCM to the browser via the audio capture WebSocket
            if self._audio_capture and self._audio_capture._server:
                # Send directly to the page's WebSocket handler
                await self._send_tts_to_browser(pcm_data)
                duration = len(pcm_data) / (16000 * 2)
                await asyncio.sleep(duration + 0.3)
                logger.info(f"ACSCallingBot {self.bot_id}: spoke for {duration:.1f}s — '{text[:50]}...'")
            else:
                logger.warning(f"ACSCallingBot {self.bot_id}: no audio channel for speak()")
        except Exception as e:
            logger.error(f"ACSCallingBot {self.bot_id}: speak error: {e}", exc_info=True)

    async def speak_streaming(self, text: str):
        """Speak with sentence-level streaming."""
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
            "duration_sec": round(self._audio_capture.duration_sec if self._audio_capture else 0.0, 1),
        }

    # ── Browser Setup ─────────────────────────────────────────────────

    async def _launch_browser(self, playwright):
        self.state = BotState.INITIALIZING
        self.status_message = "Launching browser for ACS Calling..."

        # ACS Calling SDK runs headless — WebRTC audio needs special flags
        self._browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--use-fake-ui-for-media-stream",       # Auto-allow mic/cam
                "--use-fake-device-for-media-stream",    # Provide fake audio device for WebRTC
                "--autoplay-policy=no-user-gesture-required",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--enable-features=AudioServiceOutOfProcess",  # Audio in separate process
                "--disable-features=WebRtcHideLocalIpsWithMdns",
            ],
        )

        self._context = await self._browser.new_context(
            permissions=["microphone", "camera", "notifications"],
            viewport={"width": 800, "height": 600},
        )

        self._page = await self._context.new_page()

        # Log console messages from the ACS page
        self._page.on("console", lambda msg: logger.info(
            f"ACSCallingBot {self.bot_id} [browser]: {msg.text}"
        ))

        logger.info(f"ACSCallingBot {self.bot_id}: browser launched")

    async def _join_meeting(self):
        """Get ACS token, load the page, and join the meeting."""
        self.state = BotState.JOINING
        self.status_message = "Getting ACS token..."

        try:
            # 1. Generate ACS VOIP token
            token_data = await self._get_acs_token()
            logger.info(f"ACSCallingBot {self.bot_id}: ACS token acquired")

            # 2. Start audio capture WebSocket server
            os.makedirs(self.audio_dir, exist_ok=True)
            audio_file = os.path.join(self.audio_dir, f"{self.bot_id}.wav")
            self._audio_capture = AudioCapture(output_path=audio_file)
            await self._audio_capture.start()
            ws_url = self._audio_capture.get_ws_url()
            logger.info(f"ACSCallingBot {self.bot_id}: audio WS on {ws_url}")

            # 3. Load the ACS calling HTML page from FastAPI static mount
            self.status_message = "Loading ACS Calling SDK..."
            html_url = "http://localhost:8100/acs-calling/acs_meeting.html"
            logger.info(f"ACSCallingBot {self.bot_id}: loading ACS page from {html_url}")
            await self._page.goto(html_url, timeout=120000, wait_until="load")
            # Verify the bundle loaded
            await self._page.wait_for_function(
                "typeof window.__gnevaACS !== 'undefined'",
                timeout=30000,
            )
            logger.info(f"ACSCallingBot {self.bot_id}: ACS SDK loaded")

            # 4. Call the join function
            self.status_message = "Joining Teams meeting via ACS..."
            config = {
                "token": token_data["token"],
                "meetingLink": self.meeting_url,
                "wsUrl": ws_url,
                "displayName": self.bot_name,
            }

            # Fire-and-forget the join (it's async JS, we poll for status)
            await self._page.evaluate(
                f"window.__gnevaACS.join({self._json_dumps(config)}).catch(e => console.error('[ACS] join error:', e.message))"
            )

            # 5. Wait for connection
            self.status_message = "Waiting for meeting connection..."
            connected = await self._wait_for_connection(timeout=self.lobby_timeout)

            if not connected:
                self.state = BotState.FAILED
                acs_error = await self._page.evaluate("window.__gnevaACS.error || 'Unknown error'")
                acs_status = await self._page.evaluate("window.__gnevaACS.status || 'unknown'")
                self.error = f"ACS connection failed: {acs_error} (status: {acs_status})"
                self.status_message = f"Failed to connect: {acs_error}"
                return

            self.state = BotState.IN_MEETING
            self.status_message = "Connected — starting conversation engine..."

            # 6. Start conversation engine
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
                logger.info(f"ACSCallingBot {self.bot_id}: conversation engine started")
            except Exception as e:
                logger.warning(f"ACSCallingBot {self.bot_id}: conversation engine failed: {e}")

            self.status_message = "Active — listening and recording (ACS audio)"
            logger.info(f"ACSCallingBot {self.bot_id}: in meeting via ACS Calling SDK")

        except Exception as e:
            self.state = BotState.FAILED
            self.error = str(e)
            self.status_message = f"Failed to join: {e}"
            logger.error(f"ACSCallingBot {self.bot_id}: join failed: {e}", exc_info=True)

    async def _get_acs_token(self) -> dict:
        """Create an ACS user identity and get a VOIP token."""
        from gneva.config import get_settings
        settings = get_settings()

        if not settings.acs_connection_string:
            raise RuntimeError("ACS_CONNECTION_STRING not set")

        from azure.communication.identity import CommunicationIdentityClient

        identity_client = CommunicationIdentityClient.from_connection_string(
            settings.acs_connection_string
        )
        user = identity_client.create_user()
        token_response = identity_client.get_token(user, scopes=["voip"])

        expires = token_response.expires_on
        if hasattr(expires, "isoformat"):
            expires = expires.isoformat()

        return {
            "user_id": user.properties["id"],
            "token": token_response.token,
            "expires_on": str(expires),
        }

    async def _wait_for_connection(self, timeout: int = 300) -> bool:
        """Wait for the ACS call to reach 'Connected' state."""
        deadline = datetime.utcnow() + timedelta(seconds=timeout)

        while datetime.utcnow() < deadline:
            try:
                status = await self._page.evaluate("window.__gnevaACS.status")
                if status == "Connected":
                    return True
                if status in ("failed", "Disconnected"):
                    return False
            except Exception:
                return False
            await asyncio.sleep(1)

        return False

    # ── Recording ─────────────────────────────────────────────────────

    async def _start_recording(self):
        """Wire up STT to the audio capture WebSocket."""
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

                self._audio_capture.set_audio_chunk_callback(
                    self._realtime_stt.feed_audio
                )
                logger.info(
                    f"ACSCallingBot {self.bot_id}: STT started "
                    f"({settings.stt_backend}/{settings.stt_model_size})"
                )
            except Exception as e:
                logger.warning(f"ACSCallingBot {self.bot_id}: STT init failed: {e}")
                self._realtime_stt = None

        self.state = BotState.RECORDING
        self.status_message = "Recording — real audio via ACS Calling SDK"

    async def _on_stt_utterance(self, text: str, confidence: float, track_id: int = 0):
        """STT callback — resolve speaker from ACS participant data."""
        if not self._conversation or not text.strip():
            return

        # Get speaker name from the ACS page's participant map
        speaker = "Participant"
        try:
            participants = await self._page.evaluate("window.__gnevaACS.participants")
            # The track_id maps to participant order (not ideal but workable)
            if participants and isinstance(participants, dict):
                names = list(participants.values())
                if track_id > 0 and track_id <= len(names):
                    speaker = names[track_id - 1]
                elif names:
                    speaker = names[0]
        except Exception:
            pass

        logger.debug(
            f"ACSCallingBot {self.bot_id}: STT (track={track_id}): [{speaker}] '{text[:80]}'"
        )
        await self._conversation.on_transcript_segment(text, speaker)

    # ── Monitoring ────────────────────────────────────────────────────

    async def _monitor_meeting(self):
        """Monitor ACS call state and audio."""
        deadline = datetime.utcnow() + timedelta(seconds=self.max_duration)
        last_log_time = datetime.utcnow()

        while not self._stop_event.is_set():
            # Check ACS call state
            try:
                status = await self._page.evaluate("window.__gnevaACS.status")
                if status in ("Disconnected", "ended"):
                    logger.info(f"ACSCallingBot {self.bot_id}: call ended (status={status})")
                    break
            except Exception:
                logger.info(f"ACSCallingBot {self.bot_id}: page gone — meeting ended")
                break

            if datetime.utcnow() > deadline:
                logger.info(f"ACSCallingBot {self.bot_id}: max duration reached")
                break

            # Periodic logging
            now = datetime.utcnow()
            if (now - last_log_time).total_seconds() >= 60:
                audio_info = ""
                if self._audio_capture:
                    audio_info = f", audio={self._audio_capture.duration_sec:.1f}s"
                logger.info(
                    f"ACSCallingBot {self.bot_id}: monitoring — "
                    f"status={status}{audio_info}"
                )
                last_log_time = now

            await asyncio.sleep(0.5)

    # ── Leave / Cleanup ───────────────────────────────────────────────

    async def _leave_meeting(self):
        self.state = BotState.LEAVING
        self.status_message = "Leaving meeting..."

        if self._conversation:
            try:
                await self._conversation.stop()
            except Exception:
                pass

        # Tell ACS to hang up
        try:
            if self._page and not self._page.is_closed():
                await self._page.evaluate("window.__gnevaACS.leave()")
                await asyncio.sleep(2)
        except Exception as e:
            logger.debug(f"ACSCallingBot {self.bot_id}: leave error: {e}")

        # Save audio
        if self._audio_capture:
            self.audio_path = await self._audio_capture.stop()

        # Save transcript
        has_captions = False
        if self._conversation and self._conversation._transcript_buffer:
            caption_segments = [
                {"speaker": s.get("speaker", "Unknown"), "text": s.get("text", ""), "ts": 0}
                for s in self._conversation._transcript_buffer
                if s.get("text", "").strip()
            ]
            if caption_segments and self.meeting_id:
                try:
                    await self._save_transcript(caption_segments)
                    has_captions = True
                except Exception as e:
                    logger.error(f"ACSCallingBot {self.bot_id}: transcript save failed: {e}")

        self.ended_at = datetime.utcnow()
        self.state = BotState.ENDED

        has_audio = self._audio_capture and self._audio_capture.has_audio
        success = has_audio or has_captions
        logger.info(
            f"ACSCallingBot {self.bot_id}: ended — "
            f"audio={'yes' if has_audio else 'no'}, "
            f"captions={'yes' if has_captions else 'no'}"
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
                logger.error(f"ACSCallingBot {self.bot_id}: on_complete error: {e}")

    async def _emergency_save(self):
        try:
            if self._conversation:
                try:
                    await self._conversation.stop()
                except Exception:
                    pass
            if self._audio_capture:
                self.audio_path = await self._audio_capture.stop()
            self.ended_at = datetime.utcnow()
        except Exception as e:
            logger.warning(f"ACSCallingBot {self.bot_id}: emergency save failed: {e}")

    async def _cleanup(self):
        try:
            if self._realtime_stt:
                await self._realtime_stt.stop()
        except Exception:
            pass
        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass
        logger.info(f"ACSCallingBot {self.bot_id}: cleaned up")

    # ── Audio Helpers ─────────────────────────────────────────────────

    async def _send_tts_to_browser(self, pcm_data: bytes):
        """Send PCM16 audio to the browser page via page.evaluate.

        The browser's _playTTSAudio function receives it and feeds it
        into the outgoing LocalAudioStream.
        """
        import base64
        # Send in chunks to avoid massive eval strings
        chunk_size = 16000 * 2  # 1 second at a time
        offset = 0

        while offset < len(pcm_data):
            chunk = pcm_data[offset:offset + chunk_size]
            b64 = base64.b64encode(chunk).decode()
            try:
                await self._page.evaluate(f"""
                    (() => {{
                        const b64 = "{b64}";
                        const binary = atob(b64);
                        const bytes = new Uint8Array(binary.length);
                        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
                        window.__gnevaACS._playTTSAudio(bytes);
                    }})()
                """)
            except Exception as e:
                logger.warning(f"ACSCallingBot {self.bot_id}: TTS send error: {e}")
                break
            offset += chunk_size
            await asyncio.sleep(0.05)

    def _wav_to_pcm16(self, wav_bytes: bytes) -> bytes:
        """Convert WAV to raw PCM16 mono 16kHz."""
        import io
        import wave

        try:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                frame_rate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())

            import numpy as np

            if sample_width == 2:
                samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            elif sample_width == 4:
                samples = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
            else:
                samples = np.frombuffer(frames, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

            if channels > 1:
                samples = samples.reshape(-1, channels).mean(axis=1)

            if frame_rate != 16000:
                num_samples = int(len(samples) * 16000 / frame_rate)
                indices = np.linspace(0, len(samples) - 1, num_samples)
                samples = np.interp(indices, np.arange(len(samples)), samples)

            return (samples * 32767).astype(np.int16).tobytes()

        except Exception as e:
            logger.error(f"ACSCallingBot {self.bot_id}: WAV conversion error: {e}")
            return wav_bytes

    async def _save_transcript(self, caption_segments: list):
        """Save transcript to DB."""
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
                db.add(TranscriptSegment(
                    transcript_id=transcript.id,
                    speaker_label=seg.get("speaker", "Participant"),
                    start_ms=i * 3000,
                    end_ms=(i + 1) * 3000,
                    text=text,
                    confidence=0.95,
                ))

            await db.commit()
            logger.info(
                f"ACSCallingBot {self.bot_id}: saved transcript — "
                f"{len(caption_segments)} segments"
            )

    @staticmethod
    def _json_dumps(obj):
        import json
        return json.dumps(obj)
