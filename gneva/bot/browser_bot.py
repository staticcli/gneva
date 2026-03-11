"""BrowserBot — single bot instance that joins one meeting via headless Chromium."""

import asyncio
import uuid
import logging
import os
from datetime import datetime, timedelta
from enum import Enum
from urllib.parse import urlparse, urlunparse

from gneva.bot.audio_capture import AudioCapture
from gneva.bot.avatar import get_avatar_inject_js
from gneva.bot.platforms import detect_platform, get_driver

logger = logging.getLogger(__name__)


def _redact_url(url: str) -> str:
    """Return *url* with query parameters and fragment stripped for safe logging."""
    try:
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    except Exception:
        return "<redacted-url>"


class BotState(str, Enum):
    INITIALIZING = "initializing"
    JOINING = "joining"
    IN_LOBBY = "in_lobby"
    IN_MEETING = "in_meeting"
    RECORDING = "recording"
    LEAVING = "leaving"
    ENDED = "ended"
    FAILED = "failed"


class BrowserBot:
    """A single headless browser bot that joins and records one meeting."""

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
        self.on_complete = on_complete  # async callback(bot_id, meeting_id, audio_path, success)
        self.voice_id = voice_id  # ElevenLabs voice ID for TTS
        self.org_id = org_id  # Organization ID for cross-meeting memory
        self.greeting_mode = greeting_mode  # Greeting style for join
        self.on_state_change = None  # async callback(bot_id, meeting_id, new_state)

        self._state = BotState.INITIALIZING
        self.platform = detect_platform(meeting_url)
        self.error: str | None = None
        self.started_at: datetime | None = None
        self.ended_at: datetime | None = None
        self.audio_path: str | None = None

        self._browser = None
        self._context = None
        self._page = None
        self._driver = None
        self._audio_capture: AudioCapture | None = None
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
        """Main lifecycle: launch browser → join → record → leave.

        If the bot gets removed/kicked/disconnected, we still save
        the transcript and trigger the pipeline — treat it as a normal end.
        """
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
            logger.info(f"Bot {self.bot_id} cancelled — saving transcript")
            await self._emergency_save()
            self.state = BotState.ENDED
        except Exception as e:
            logger.error(f"Bot {self.bot_id} error: {e}", exc_info=True)
            # Still try to save whatever transcript we have
            await self._emergency_save()
            self.state = BotState.FAILED
            self.error = str(e)
        finally:
            await self._cleanup()

    async def stop(self):
        """Signal the bot to leave and stop."""
        self._stop_event.set()

    async def _launch_browser(self, playwright):
        """Create a browser context with the right flags for meeting audio."""
        self.state = BotState.INITIALIZING

        # Use headed mode on Windows for speech recognition + audio
        import sys
        use_headless = sys.platform != "win32"
        self._browser = await playwright.chromium.launch(
            headless=use_headless,
            args=[
                "--use-fake-ui-for-media-stream",       # Auto-approve mic/camera permission prompts
                "--autoplay-policy=no-user-gesture-required",
                "--disable-features=WebRtcHideLocalIpsWithMdns",
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--auto-select-desktop-capture-source=Entire screen",
                "--enable-usermedia-screen-capturing",
                "--disable-external-intent-requests",    # Block "open in app?" protocol popups
                "--disable-popup-blocking",              # We handle popups ourselves
                "--block-new-web-contents",              # Prevent new windows opening
            ],
        )

        self._context = await self._browser.new_context(
            permissions=["microphone", "camera", "notifications"],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
        )

        # Override navigator.webdriver to avoid detection
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
        """)

        # Inject avatar system — overrides getUserMedia to serve canvas-based face
        face_b64 = None
        try:
            from gneva.bot.talking_head import get_talking_head_service
            ths = get_talking_head_service()
            # Use voice_id if set, otherwise fall back to default voice's face
            voice_for_face = self.voice_id
            if not voice_for_face:
                # Get default voice from settings API voice store
                from gneva.api.settings import _DEFAULT_VOICES
                default_v = next((v for v in _DEFAULT_VOICES if v.get("is_default")), None)
                if default_v:
                    voice_for_face = default_v["id"]
            face_b64 = ths.get_face_b64(voice_for_face)
            if face_b64:
                logger.info(f"Bot {self.bot_id}: loaded face image for voice {voice_for_face}")
            else:
                # Last resort: get any available face
                face_b64 = ths.get_face_b64(None)
                if face_b64:
                    logger.info(f"Bot {self.bot_id}: loaded fallback face image")
        except Exception as e:
            logger.warning(f"Bot {self.bot_id}: could not load face image: {e}")
        avatar_js = get_avatar_inject_js(face_image_b64=face_b64)
        await self._context.add_init_script(avatar_js)

        # Inject audio capture hook EARLY (init_script) so it intercepts
        # RTCPeerConnection BEFORE Teams creates its peer connections.
        # The WebSocket URL is set later via page.evaluate once the WS server starts.
        await self._context.add_init_script("""
        (function() {
            // Hook RTCPeerConnection to capture incoming audio tracks
            const OrigRTC = window.RTCPeerConnection;
            if (!OrigRTC) return;

            window.__gnevaIncomingAudioTracks = [];

            window.RTCPeerConnection = function(...args) {
                const pc = new OrigRTC(...args);

                pc.addEventListener('track', (event) => {
                    if (event.track.kind === 'audio' && event.streams.length > 0) {
                        console.log('[Gneva Audio] Captured incoming WebRTC audio track');
                        window.__gnevaIncomingAudioTracks.push(event.streams[0]);

                        // Connect to audio capture if ready
                        if (window.__gnevaAudioCaptureMerger && window.__gnevaAudioCaptureCtx) {
                            try {
                                const src = window.__gnevaAudioCaptureCtx.createMediaStreamSource(event.streams[0]);
                                src.connect(window.__gnevaAudioCaptureMerger);
                                console.log('[Gneva Audio] Connected incoming track to capture pipeline');
                            } catch(e) {
                                console.warn('[Gneva Audio] Track connect failed:', e.message);
                            }
                        }
                    }
                });

                return pc;
            };
            window.RTCPeerConnection.prototype = OrigRTC.prototype;
            Object.getOwnPropertyNames(OrigRTC).forEach(prop => {
                if (prop !== 'prototype' && prop !== 'length' && prop !== 'name') {
                    try { window.RTCPeerConnection[prop] = OrigRTC[prop]; } catch(e) {}
                }
            });

            console.log('[Gneva Audio] RTCPeerConnection hook installed (early)');
        })();
        """)

        self._page = await self._context.new_page()
        self._driver = get_driver(self.platform, self._page, self.bot_name)

        logger.info(f"Bot {self.bot_id}: browser launched for {self.platform} -> {_redact_url(self.meeting_url)}")

    async def _join_meeting(self):
        """Join the meeting using the platform driver."""
        self.state = BotState.JOINING

        success = await self._driver.join(self.meeting_url)
        if not success:
            # Save diagnostic screenshot before cleanup
            try:
                if self._page:
                    os.makedirs(os.path.join(self.audio_dir, "diagnostics"), exist_ok=True)
                    spath = os.path.join(self.audio_dir, "diagnostics", f"{self.bot_id}_join_failed.png")
                    await self._page.screenshot(path=spath, full_page=True)
                    logger.info(f"Bot {self.bot_id}: join-fail screenshot saved to {spath}")
                    logger.info(f"Bot {self.bot_id}: page URL at failure: {_redact_url(self._page.url)}")
            except Exception:
                pass

            # Last-ditch: wait a bit and check if we're actually in the meeting
            # (Teams light-meetings can auto-join with a delay)
            logger.info(f"Bot {self.bot_id}: driver reported join failure — waiting 10s for possible late auto-join")
            await asyncio.sleep(10)
            if hasattr(self._driver, '_is_already_in_meeting') and await self._driver._is_already_in_meeting():
                logger.info(f"Bot {self.bot_id}: late auto-join detected — proceeding as joined")
                success = True
            else:
                self.state = BotState.FAILED
                self.error = "Failed to join meeting"
                return

        # Wait in lobby if needed
        lobby_start = datetime.utcnow()
        while await self._driver.is_in_lobby():
            self.state = BotState.IN_LOBBY
            elapsed = (datetime.utcnow() - lobby_start).total_seconds()
            if elapsed > self.lobby_timeout:
                self.state = BotState.FAILED
                self.error = "Lobby timeout — host did not admit the bot"
                return
            if self._stop_event.is_set():
                return
            await asyncio.sleep(5)

        self.state = BotState.IN_MEETING

        # Start conversation engine for live responses
        try:
            from gneva.bot.conversation import ConversationEngine
            self._conversation = ConversationEngine(
                bot=self,
                org_id=str(self.org_id) if self.org_id else None,
                greeting_mode=self.greeting_mode,
            )
            await self._conversation.start()
            await self._conversation.greet()
            logger.info(f"Bot {self.bot_id}: conversation engine started")
        except Exception as e:
            logger.warning(f"Bot {self.bot_id}: conversation engine failed to start: {e}")

        # Enable live captions so we can "hear" what people say
        try:
            if hasattr(self._driver, 'enable_live_captions'):
                await self._driver.enable_live_captions()
                logger.info(f"Bot {self.bot_id}: live captions enabled")
        except Exception as e:
            logger.warning(f"Bot {self.bot_id}: could not enable live captions: {e}")

        # Keep chat pane open so we can monitor messages
        try:
            await self._driver._click_if_visible(
                "button[aria-label*='Chat' i], button[id*='chat' i], button[aria-label*='Show conversation' i]",
                timeout=3000
            )
            logger.info(f"Bot {self.bot_id}: opened chat pane")
        except Exception:
            pass

        # Force-inject avatar stream into self-video element (belt-and-suspenders)
        try:
            await self._page.evaluate("""
                (() => {
                    // Find self-view video elements and replace their srcObject
                    const selfVideos = document.querySelectorAll(
                        'video[id*="self" i], video[id*="local" i], video[class*="self" i], ' +
                        'video[data-tid*="self" i], video[data-cid*="self" i]'
                    );
                    if (selfVideos.length === 0) {
                        console.log('[Gneva Avatar] No self-video elements found (may be thumbnailed)');
                    }
                    selfVideos.forEach(v => {
                        const canvas = document.querySelector('canvas');
                        if (canvas) {
                            const stream = canvas.captureStream(30);
                            v.srcObject = stream;
                            console.log('[Gneva Avatar] Injected canvas stream into self-video element');
                        }
                    });
                })();
            """)
        except Exception as e:
            logger.debug(f"Bot {self.bot_id}: avatar post-injection: {e}")

        # Post consent message
        try:
            await self._driver.post_chat_message(self.consent_message)
        except Exception as e:
            from gneva.config import get_settings
            _settings = get_settings()
            if _settings.bot_consent_required:
                self.state = BotState.FAILED
                self.error = f"Consent message required but failed to post: {e}"
                logger.error(f"Bot {self.bot_id}: consent required but failed: {e}")
                return
            logger.warning(f"Could not post consent message: {e}")

        logger.info(f"Bot {self.bot_id}: in meeting")

    async def _start_recording(self):
        """Inject audio capture JS and start recording."""
        os.makedirs(self.audio_dir, exist_ok=True)
        audio_file = os.path.join(self.audio_dir, f"{self.bot_id}.wav")

        self._audio_capture = AudioCapture(output_path=audio_file)
        await self._audio_capture.start()

        # Inject the audio capture JS via CDP
        js_code = self._audio_capture.get_inject_js()
        cdp = await self._page.context.new_cdp_session(self._page)
        await cdp.send("Runtime.evaluate", {"expression": js_code})

        self.state = BotState.RECORDING
        logger.info(f"Bot {self.bot_id}: recording started, audio WS on port {self._audio_capture.port}")

        # Inject listening system for conversation engine
        # Three methods: 1) Route incoming WebRTC audio → Web Speech API for voice
        #                2) Scrape Teams captions    3) Scrape Teams chat
        if self._conversation:
            caption_js = """
            (function() {
                window.__gnevaCaptions = { segments: [] };
                const seenTexts = new Set();
                let lastCaptionSnapshot = '';

                // === TEAMS CAPTION SCRAPER ===
                // Exact DOM structure (from live inspection):
                //   [data-tid="closed-caption-v2-virtual-list-content"]
                //     > flex containers, each containing:
                //       > speaker name span (sibling before [data-tid="closed-caption-text"])
                //       > [data-tid="closed-caption-text"] span with the actual text

                function scrapeCaptions() {
                    const textEls = document.querySelectorAll('[data-tid="closed-caption-text"]');
                    if (textEls.length === 0) return;

                    textEls.forEach(textEl => {
                        const text = (textEl.textContent || '').trim();
                        if (!text || text.length < 3) return;

                        // Walk up to find the caption entry container and extract speaker
                        let speaker = 'Participant';
                        let container = textEl.parentElement;

                        // Walk up max 4 levels to find the entry container with speaker name
                        for (let i = 0; i < 4 && container; i++) {
                            // Look for speaker name — it's a text node/span BEFORE the caption text
                            const allText = container.innerText || '';
                            if (allText.length > text.length + 3) {
                                // The speaker name is the text before the caption text
                                const idx = allText.indexOf(text);
                                if (idx > 0) {
                                    const nameCandidate = allText.substring(0, idx).trim();
                                    // Clean up: remove emoji/icons, "(Unverified)" etc
                                    const cleanName = nameCandidate
                                        .replace(/\\(Unverified\\)/gi, '')
                                        .replace(/[\\u{1F3A7}\\u{1F50A}\\u{1F399}]/gu, '')
                                        .trim();
                                    if (cleanName && cleanName.length > 1 && cleanName.length < 50) {
                                        speaker = cleanName;
                                        break;
                                    }
                                }
                            }
                            container = container.parentElement;
                        }

                        // Skip Gneva's own captions
                        const spkLower = speaker.toLowerCase();
                        if (spkLower.includes('gneva') || spkLower.includes('geneva') ||
                            spkLower.includes('neva ai') || spkLower.includes('gneva ai')) return;

                        // Also skip if the TEXT looks like Gneva's greeting
                        const txtLower = text.toLowerCase();
                        if (txtLower.includes('i\\'m neva') || txtLower.includes('i\\'m gneva') ||
                            txtLower.includes('i am gneva') || txtLower.includes('i am neva')) return;

                        // Skip system messages
                        if (txtLower.includes('is recording') || txtLower.includes('joined the') ||
                            txtLower.includes('transcription has started') ||
                            txtLower.includes('captions will now') || txtLower.includes('left the meeting')) return;

                        // Deduplicate by exact text
                        const key = speaker + '|' + text;
                        if (seenTexts.has(key)) return;
                        seenTexts.add(key);

                        // Bound the set
                        if (seenTexts.size > 300) {
                            const it = seenTexts.values();
                            for (let i = 0; i < 100; i++) seenTexts.delete(it.next().value);
                        }

                        console.log('[Gneva Caption] ' + speaker + ': ' + text);
                        window.__gnevaCaptions.segments.push({
                            text: text, speaker: speaker, ts: Date.now()
                        });

                        // Cap segment buffer to prevent unbounded memory growth
                        if (window.__gnevaCaptions.segments.length > 500) {
                            window.__gnevaCaptions.segments.splice(0, 200);
                        }
                    });
                }

                // Poll every 800ms for responsive conversation
                setInterval(scrapeCaptions, 500);  // 500ms for near-realtime

                // === CHAT SCRAPER (backup) ===
                const seenChat = new Set();
                function scrapeChat() {
                    document.querySelectorAll(
                        '[data-tid="messageBodyContent"], .fui-ChatMessage__body'
                    ).forEach(el => {
                        const text = (el.textContent || '').trim();
                        if (!text || text.length < 2 || seenChat.has(text)) return;
                        if (text.includes('Gneva AI') || text.includes('joined')) return;
                        seenChat.add(text);
                        if (seenChat.size > 200) {
                            seenChat.delete(seenChat.values().next().value);
                        }
                        window.__gnevaCaptions.segments.push({
                            text: text, speaker: 'Chat', ts: Date.now()
                        });
                    });
                }
                setInterval(scrapeChat, 3000);

                console.log('[Gneva] Caption scraper initialized (data-tid selectors)');
            })();
            """
            try:
                await cdp.send("Runtime.evaluate", {"expression": caption_js})
                logger.info(f"Bot {self.bot_id}: caption scraper injected")
            except Exception as e:
                logger.warning(f"Bot {self.bot_id}: caption scraper injection failed: {e}")

    async def _monitor_meeting(self):
        """Poll for meeting end, stop signal, or max duration.

        Fallbacks beyond CSS selectors:
        - No audio for 60+ seconds while recording -> meeting likely ended
        - Page URL changed (redirected away) -> meeting ended
        - Periodic state logging for debugging
        """
        deadline = datetime.utcnow() + timedelta(seconds=self.max_duration)
        initial_url = self._page.url if self._page else ""
        last_audio_bytes = self._audio_capture._total_bytes if self._audio_capture else 0
        last_audio_change = datetime.utcnow()
        last_log_time = datetime.utcnow()
        silence_threshold_sec = 7200  # 2 hours — captions work independently of audio capture
        poll_count = 0

        while not self._stop_event.is_set():
            poll_count += 1

            # Check if meeting ended via platform driver selectors
            try:
                if await self._driver.detect_meeting_ended():
                    logger.info(f"Bot {self.bot_id}: meeting ended (detected by driver)")
                    break
            except Exception as e:
                logger.warning(f"Bot {self.bot_id}: detect_meeting_ended error: {e}")

            # Check if bot was removed/kicked from the meeting
            try:
                if self._page:
                    removed = await self._page.evaluate("""
                        (() => {
                            const body = document.body ? document.body.innerText.toLowerCase() : '';
                            const removedPhrases = [
                                'you have been removed', 'removed from the meeting',
                                'the meeting has ended', 'you were removed',
                                'kicked from', 'call ended', 'meeting ended',
                                'you left the meeting', 'disconnected from the meeting',
                                'the organizer ended the meeting',
                            ];
                            return removedPhrases.some(p => body.includes(p));
                        })()
                    """)
                    if removed:
                        logger.info(f"Bot {self.bot_id}: removed/kicked from meeting")
                        break
            except Exception:
                # Page might be gone — that itself means we got removed
                if self._page and self._page.is_closed():
                    logger.info(f"Bot {self.bot_id}: page closed — removed from meeting")
                    break

            # Fallback: check if page URL has changed (redirected away from meeting)
            try:
                current_url = self._page.url if self._page else ""
                if initial_url and current_url and current_url != initial_url:
                    # URL changed — check if it looks like we left the meeting
                    if not any(
                        domain in current_url.lower()
                        for domain in [
                            "teams.microsoft.com", "teams.live.com",
                            "zoom.us", "zoom.com",
                            "meet.google.com",
                        ]
                    ):
                        logger.info(
                            f"Bot {self.bot_id}: meeting ended — URL changed "
                            f"from {_redact_url(initial_url)} to {_redact_url(current_url)}"
                        )
                        break
            except Exception:
                pass

            # Fallback: detect audio silence timeout
            if self._audio_capture and self.state == BotState.RECORDING:
                current_bytes = self._audio_capture._total_bytes
                if current_bytes > last_audio_bytes:
                    last_audio_bytes = current_bytes
                    last_audio_change = datetime.utcnow()
                else:
                    silence_sec = (datetime.utcnow() - last_audio_change).total_seconds()
                    if silence_sec >= silence_threshold_sec:
                        logger.info(
                            f"Bot {self.bot_id}: no audio for {silence_sec:.0f}s — "
                            f"assuming meeting ended (silence timeout)"
                        )
                        break

            # Check max duration
            if datetime.utcnow() > deadline:
                logger.info(f"Bot {self.bot_id}: max duration reached")
                break

            # Periodic debug logging (every ~60 seconds = 30 polls at 2s interval)
            now = datetime.utcnow()
            if (now - last_log_time).total_seconds() >= 60:
                audio_info = ""
                if self._audio_capture:
                    audio_info = (
                        f", audio={self._audio_capture.duration_sec:.1f}s "
                        f"({self._audio_capture._total_bytes / 1024:.0f} KB)"
                    )
                elapsed = (now - self.started_at).total_seconds() if self.started_at else 0
                logger.info(
                    f"Bot {self.bot_id}: monitoring — state={self.state.value}, "
                    f"elapsed={elapsed:.0f}s, polls={poll_count}{audio_info}"
                )
                last_log_time = now

            # Poll for caption segments and feed to conversation engine
            if self._conversation and self._page:
                try:
                    result = await self._page.evaluate("""
                        (() => {
                            if (!window.__gnevaCaptions || !window.__gnevaCaptions.segments.length) return [];
                            const segs = window.__gnevaCaptions.segments.splice(0);
                            return segs;
                        })()
                    """)
                    if result:
                        for seg in result:
                            text = seg.get("text", "")
                            speaker = seg.get("speaker", "Unknown")
                            if text.strip():
                                await self._conversation.on_transcript_segment(text, speaker)
                except Exception as e:
                    if poll_count % 12 == 0:  # Log only every ~60s
                        logger.debug(f"Bot {self.bot_id}: caption poll error: {e}")

            await asyncio.sleep(1)  # Poll every 1s for near-realtime conversation

    async def _emergency_save(self):
        """Save whatever transcript/context we have when the bot is unexpectedly disconnected.

        Called on CancelledError or unexpected exceptions — the page may already be
        gone, so we only use what's in memory (conversation engine buffer).
        """
        try:
            # Save conversation engine's context
            if self._conversation:
                try:
                    await self._conversation.stop()
                except Exception:
                    pass

                # Try to save the transcript buffer directly
                if self._conversation._transcript_buffer and self.meeting_id:
                    caption_segments = [
                        {"speaker": s.get("speaker", "Unknown"), "text": s.get("text", ""), "ts": 0}
                        for s in self._conversation._transcript_buffer
                        if s.get("text", "").strip()
                    ]
                    if caption_segments:
                        try:
                            await self._save_caption_transcript(caption_segments)
                            logger.info(
                                f"Bot {self.bot_id}: emergency saved {len(caption_segments)} caption segments"
                            )
                        except Exception as e:
                            logger.warning(f"Bot {self.bot_id}: emergency transcript save failed: {e}")

            # Save audio if we have any
            if self._audio_capture:
                try:
                    self.audio_path = await self._audio_capture.stop()
                except Exception:
                    pass

            # Trigger pipeline
            self.ended_at = datetime.utcnow()
            if self.on_complete and self.meeting_id:
                try:
                    has_audio = self._audio_capture.has_audio if self._audio_capture else False
                    await self.on_complete(
                        bot_id=self.bot_id,
                        meeting_id=self.meeting_id,
                        audio_path=self.audio_path,
                        success=True,  # We have data worth processing
                    )
                except Exception as e:
                    logger.debug(f"Bot {self.bot_id}: emergency on_complete failed: {e}")

        except Exception as e:
            logger.warning(f"Bot {self.bot_id}: emergency save failed: {e}")

    async def _leave_meeting(self):
        """Leave the meeting and finalize audio + caption transcript."""
        self.state = BotState.LEAVING

        # Stop conversation engine
        if self._conversation:
            try:
                await self._conversation.stop()
            except Exception:
                pass

        # Extract caption transcript from browser BEFORE closing it
        caption_segments = []
        if self._page and self._conversation:
            try:
                caption_segments = await self._page.evaluate("""
                    (() => {
                        // Gather all caption segments from conversation engine buffer
                        // plus any remaining in the scraper buffer
                        const result = [];
                        if (window.__gnevaCaptions && window.__gnevaCaptions.segments) {
                            window.__gnevaCaptions.segments.forEach(s => {
                                result.push({text: s.text, speaker: s.speaker, ts: s.ts});
                            });
                        }
                        return result;
                    })()
                """)
            except Exception as e:
                logger.warning(f"Bot {self.bot_id}: caption extraction failed: {e}")

        # Also include the conversation engine's transcript buffer
        if self._conversation and self._conversation._transcript_buffer:
            for seg in self._conversation._transcript_buffer:
                # Avoid duplicates — only add if not already in caption_segments
                text = seg.get("text", "")
                if text and not any(c.get("text") == text for c in caption_segments):
                    caption_segments.append(seg)

        try:
            await self._driver.leave()
        except Exception as e:
            logger.warning(f"Bot {self.bot_id}: leave error: {e}")

        # Save audio
        if self._audio_capture:
            self.audio_path = await self._audio_capture.stop()
            logger.info(
                f"Bot {self.bot_id}: audio saved "
                f"({self._audio_capture.duration_sec:.1f}s)"
            )

            # If no audio was captured, save diagnostic info
            if not self._audio_capture.has_audio:
                await self._save_diagnostics()

        # Save caption transcript to database
        has_captions = len(caption_segments) > 0
        if has_captions and self.meeting_id:
            try:
                await self._save_caption_transcript(caption_segments)
            except Exception as e:
                logger.error(f"Bot {self.bot_id}: caption transcript save failed: {e}")

        self.ended_at = datetime.utcnow()
        self.state = BotState.ENDED

        has_audio = self._audio_capture.has_audio if self._audio_capture else False
        success = has_audio or has_captions
        logger.info(
            f"Bot {self.bot_id}: meeting ended — "
            f"audio={'yes' if has_audio else 'no'}, "
            f"captions={len(caption_segments)} segments, "
            f"success={success}"
        )

        # Trigger pipeline callback
        if self.on_complete:
            try:
                await self.on_complete(
                    bot_id=self.bot_id,
                    meeting_id=self.meeting_id,
                    audio_path=self.audio_path,
                    success=success,
                )
            except Exception as e:
                logger.error(f"Bot {self.bot_id}: on_complete callback error: {e}")

    async def _save_caption_transcript(self, caption_segments: list):
        """Save live caption segments as a transcript in the database."""
        import uuid as uuid_mod
        from gneva.db import async_session_factory
        from gneva.models.meeting import Transcript, TranscriptSegment

        meeting_uuid = uuid_mod.UUID(self.meeting_id)

        # Build full text from segments
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

            # Create individual segments with timestamps
            for i, seg in enumerate(caption_segments):
                text = seg.get("text", "").strip()
                if not text:
                    continue
                speaker = seg.get("speaker", "Participant")
                ts = seg.get("ts", 0)
                # Convert JS timestamp to ms offset from first segment
                first_ts = caption_segments[0].get("ts", 0) if caption_segments else 0
                offset_ms = int(ts - first_ts) if ts and first_ts else i * 3000

                db.add(TranscriptSegment(
                    transcript_id=transcript.id,
                    speaker_label=speaker,
                    start_ms=offset_ms,
                    end_ms=offset_ms + 3000,
                    text=text,
                    confidence=0.85,  # caption-based (slightly lower than whisper)
                ))

            await db.commit()
            logger.info(
                f"Bot {self.bot_id}: saved caption transcript — "
                f"{len(caption_segments)} segments, {len(full_text)} chars"
            )

    async def _save_diagnostics(self):
        """Save screenshot and page content when no audio was captured, for debugging."""
        diag_dir = os.path.join(self.audio_dir, "diagnostics")
        os.makedirs(diag_dir, exist_ok=True)
        prefix = os.path.join(diag_dir, self.bot_id)

        try:
            if self._page:
                # Screenshot
                screenshot_path = f"{prefix}_screenshot.png"
                await self._page.screenshot(path=screenshot_path, full_page=True)
                logger.info(f"Bot {self.bot_id}: diagnostic screenshot saved to {screenshot_path}")

                # Page content
                content_path = f"{prefix}_page.html"
                content = await self._page.content()
                with open(content_path, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.info(f"Bot {self.bot_id}: diagnostic page content saved to {content_path}")

                # Console log from the page
                url = self._page.url
                logger.warning(
                    f"Bot {self.bot_id}: NO AUDIO captured. "
                    f"Current URL: {_redact_url(url)}. "
                    f"Diagnostics saved to {diag_dir}. "
                    f"Audio capture via WebSocket may have failed — "
                    f"check if WebRTC tracks were intercepted."
                )
        except Exception as e:
            logger.warning(f"Bot {self.bot_id}: failed to save diagnostics: {e}")

    async def _cleanup(self):
        """Close browser and free resources."""
        try:
            if self._audio_capture and self._audio_capture._running:
                await self._audio_capture.stop()
        except Exception:
            pass

        try:
            if self._context:
                await self._context.close()
        except Exception:
            pass

        try:
            if self._browser:
                await self._browser.close()
        except Exception:
            pass

        logger.info(f"Bot {self.bot_id}: cleaned up")

    async def speak(self, text: str):
        """Synthesize speech via TTS and play it into the meeting.

        Injects audio into the meeting via a MediaStream audio source.
        """
        if not self._page or self.state not in (BotState.IN_MEETING, BotState.RECORDING):
            logger.warning(f"Bot {self.bot_id}: cannot speak — not in meeting")
            return

        try:
            # Unmute before speaking (like a real person)
            try:
                await self._driver.ensure_unmuted()
            except Exception as e:
                logger.debug(f"Bot {self.bot_id}: unmute attempt: {e}")

            from gneva.services.tts import TTSService, EDGE_TTS_VOICES
            import json as _json
            tts = TTSService()
            if self.voice_id:
                tts._el_voice = self.voice_id
                # Map ElevenLabs voice IDs to edge-tts voices for fallback
                from gneva.bot.talking_head import VOICE_FACE_MAP
                face_name = VOICE_FACE_MAP.get(self.voice_id, "").replace(".jpg", "")
                if face_name in EDGE_TTS_VOICES:
                    tts._edge_voice = EDGE_TTS_VOICES[face_name]
            audio_bytes = await tts.synthesize(text)

            # Convert WAV to base64 for browser injection
            import base64
            audio_b64 = base64.b64encode(audio_bytes).decode()
            audio_b64_safe = _json.dumps(audio_b64)  # S2 fix: safe JS string

            # Pipe TTS audio into the meeting via the getUserMedia audio destination
            # The avatar system provides __gnevaAudioDest which Teams uses as "mic"
            cdp = await self._page.context.new_cdp_session(self._page)
            play_js = f"""
            (async () => {{
                try {{
                    const b64 = {audio_b64_safe};
                    const binary = atob(b64);
                    const bytes = new Uint8Array(binary.length);
                    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

                    const audioCtx = window.__gnevaAudioCtx || new AudioContext();

                    if (audioCtx.state === 'suspended') {{
                        await audioCtx.resume();
                    }}

                    const buffer = await audioCtx.decodeAudioData(bytes.buffer.slice(0));
                    const source = audioCtx.createBufferSource();
                    source.buffer = buffer;

                    if (window.__gnevaAudioDest) {{
                        source.connect(window.__gnevaAudioDest);
                    }}
                    source.connect(audioCtx.destination);
                    source.start();

                    window.__gnevaLastSpeechDuration = buffer.duration;
                    return buffer.duration;
                }} catch(e) {{
                    console.error('[Gneva] Speech playback error:', e);
                    return 3;
                }}
            }})()
            """
            dur_result = await cdp.send("Runtime.evaluate", {
                "expression": play_js,
                "returnByValue": True,
                "awaitPromise": True,
            })
            duration = dur_result.get("result", {}).get("value", 3)
            await asyncio.sleep(duration + 0.5)
            logger.info(f"Bot {self.bot_id}: spoke for {duration:.1f}s — '{text[:50]}...'")

            # Re-mute after speaking (like a real person)
            try:
                await self._driver.ensure_muted()
            except Exception as e:
                logger.debug(f"Bot {self.bot_id}: re-mute attempt: {e}")
        except Exception as e:
            logger.error(f"Bot {self.bot_id}: speak error: {e}", exc_info=True)
            # Re-mute on error too
            try:
                await self._driver.ensure_muted()
            except Exception:
                pass

    def to_dict(self) -> dict:
        """Return bot status as a dict."""
        return {
            "bot_id": self.bot_id,
            "meeting_id": self.meeting_id,
            "state": self.state.value,
            "platform": self.platform,
            "bot_name": self.bot_name,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "audio_path": self.audio_path,
            "duration_sec": (
                self._audio_capture.duration_sec if self._audio_capture else 0
            ),
        }
