"""Real-time streaming speech-to-text using Whisper or Deepgram.

Receives PCM16 audio chunks from the WebSocket audio capture,
runs streaming transcription, and fires callbacks with partial/final results.

Supports per-track audio buffers so each speaker's audio is transcribed
independently. When an utterance is detected, the callback receives the
track_id so the caller can attribute it to a speaker.

This replaces the caption-scraping approach for much lower latency:
- Caption scraping: ~3-5s delay (Teams STT -> DOM render -> JS scrape -> Python poll)
- Direct audio STT: ~0.3-1s delay (audio chunk -> Whisper/Deepgram -> callback)
"""

import asyncio
import logging
import time
import struct
import numpy as np
from collections import deque
from typing import Callable, Coroutine, Any

logger = logging.getLogger(__name__)

# Minimum audio duration (seconds) before attempting transcription
MIN_CHUNK_DURATION = 0.5
# Maximum audio buffer before forcing transcription
MAX_CHUNK_DURATION = 5.0
# Silence threshold (RMS below this = silence)
# Low threshold for WebRTC audio — remote audio can be quiet
SILENCE_RMS_THRESHOLD = 30
# How long silence must last to trigger end-of-utterance (seconds)
SILENCE_DURATION_FOR_FLUSH = 0.6
# Sample rate must match audio_capture.js
SAMPLE_RATE = 16000


class _TrackBuffer:
    """Per-track audio buffer with independent VAD state."""

    def __init__(self, track_id: int):
        self.track_id = track_id
        self.audio_buffer = bytearray()
        self.buffer_start_time = time.time()
        self.silence_start = time.time()
        self.is_speaking = False


class RealtimeSTT:
    """Streaming speech-to-text engine that processes live audio.

    Maintains separate audio buffers per track_id so each speaker's audio
    is transcribed independently. When an utterance is detected, the callback
    receives (text, confidence, track_id).

    Uses faster-whisper (local, free) by default, with Deepgram as an option.
    """

    def __init__(self,
                 on_utterance: Callable[..., Coroutine[Any, Any, None]],
                 on_partial: Callable[[str], Coroutine[Any, Any, None]] | None = None,
                 backend: str = "whisper",
                 model_size: str = "base",
                 language: str = "en"):
        """
        Args:
            on_utterance: async callback(text, confidence, track_id=0) called when an utterance is detected.
                          The track_id parameter identifies which audio track produced the utterance.
            on_partial: async callback(text) for partial results (not all backends support this)
            backend: "whisper" (local) or "deepgram" (cloud, lower latency)
            model_size: Whisper model size -- "tiny" (fastest), "base" (good balance), "small" (best quality)
            language: Language code
        """
        self.on_utterance = on_utterance
        self.on_partial = on_partial
        self._backend = backend
        self._model_size = model_size
        self._language = language

        self._running = False

        # Per-track buffers: track_id -> _TrackBuffer
        self._track_buffers: dict[int, _TrackBuffer] = {}

        # Whisper model (loaded lazily)
        self._whisper_model = None

        # Processing queue -- audio chunks go here as (pcm_bytes, track_id)
        self._queue: asyncio.Queue = asyncio.Queue()
        self._process_task: asyncio.Task | None = None

        # Stats
        self._total_utterances = 0
        self._total_audio_sec = 0.0

    def _get_track_buffer(self, track_id: int) -> _TrackBuffer:
        """Get or create a buffer for the given track."""
        if track_id not in self._track_buffers:
            self._track_buffers[track_id] = _TrackBuffer(track_id)
            logger.info(f"RealtimeSTT: new track buffer created for track_id={track_id} "
                        f"(total tracks: {len(self._track_buffers)})")
        return self._track_buffers[track_id]

    async def start(self):
        """Start the STT processing loop."""
        self._running = True

        # Pre-load whisper model
        if self._backend == "whisper":
            await self._load_whisper()

        self._process_task = asyncio.create_task(self._process_loop())
        logger.info(f"RealtimeSTT started (backend={self._backend}, model={self._model_size})")

    async def stop(self):
        """Stop STT and flush remaining audio."""
        self._running = False

        # Flush remaining buffers for all tracks
        for track_id, tb in self._track_buffers.items():
            if len(tb.audio_buffer) > SAMPLE_RATE * 2 * MIN_CHUNK_DURATION:
                await self._transcribe_buffer(tb)

        if self._process_task and not self._process_task.done():
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass

        logger.info(f"RealtimeSTT stopped: {self._total_utterances} utterances, "
                    f"{self._total_audio_sec:.1f}s audio processed, "
                    f"{len(self._track_buffers)} tracks")

    def feed_audio(self, pcm_bytes: bytes, track_id: int = 0):
        """Feed raw PCM16 audio data with an optional track identifier.

        Args:
            pcm_bytes: Raw PCM16 mono 16kHz audio bytes
            track_id: Track/speaker identifier (0 = mixed/unknown)
        """
        if not self._running:
            return
        self._queue.put_nowait((pcm_bytes, track_id))

    async def _process_loop(self):
        """Main processing loop -- receives audio per-track, detects speech boundaries, transcribes."""
        while self._running:
            try:
                # Wait for audio data with timeout
                try:
                    pcm_bytes, track_id = await asyncio.wait_for(self._queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    # No audio -- check all track buffers for pending flushes
                    for tb in list(self._track_buffers.values()):
                        if tb.audio_buffer and not tb.is_speaking:
                            buffer_duration = len(tb.audio_buffer) / (SAMPLE_RATE * 2)
                            if buffer_duration >= MIN_CHUNK_DURATION:
                                await self._transcribe_buffer(tb)
                    continue

                # Get the buffer for this track
                tb = self._get_track_buffer(track_id)

                # Append to track's buffer
                tb.audio_buffer.extend(pcm_bytes)

                # Voice Activity Detection -- check if this chunk has speech
                rms = self._compute_rms(pcm_bytes)
                now = time.time()

                if rms > SILENCE_RMS_THRESHOLD:
                    # Voice detected
                    if not tb.is_speaking:
                        tb.is_speaking = True
                        tb.buffer_start_time = now
                    tb.silence_start = now
                else:
                    # Silence
                    silence_duration = now - tb.silence_start

                    if tb.is_speaking and silence_duration >= SILENCE_DURATION_FOR_FLUSH:
                        # End of utterance -- speaker stopped talking
                        tb.is_speaking = False
                        buffer_duration = len(tb.audio_buffer) / (SAMPLE_RATE * 2)

                        if buffer_duration >= MIN_CHUNK_DURATION:
                            await self._transcribe_buffer(tb)

                # Force flush if buffer is getting too long (speaker hasn't paused)
                buffer_duration = len(tb.audio_buffer) / (SAMPLE_RATE * 2)
                if buffer_duration >= MAX_CHUNK_DURATION:
                    await self._transcribe_buffer(tb)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"STT process error: {e}")
                await asyncio.sleep(0.1)

    def _compute_rms(self, pcm_bytes: bytes) -> float:
        """Compute RMS (root mean square) of PCM16 audio -- measures loudness."""
        if len(pcm_bytes) < 4:
            return 0.0
        samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        return float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))

    async def _transcribe_buffer(self, tb: _TrackBuffer):
        """Transcribe a track's audio buffer and fire callback with track_id."""
        if not tb.audio_buffer:
            return

        audio_data = bytes(tb.audio_buffer)
        tb.audio_buffer.clear()

        duration = len(audio_data) / (SAMPLE_RATE * 2)
        self._total_audio_sec += duration

        if duration < MIN_CHUNK_DURATION:
            return

        try:
            if self._backend == "whisper":
                text, confidence = await self._transcribe_whisper(audio_data)
            elif self._backend == "deepgram":
                text, confidence = await self._transcribe_deepgram(audio_data)
            else:
                logger.warning(f"Unknown STT backend: {self._backend}")
                return

            if text and len(text.strip()) > 1:
                self._total_utterances += 1
                await self.on_utterance(text.strip(), confidence, tb.track_id)

        except Exception as e:
            logger.error(f"Transcription failed (track {tb.track_id}): {e}")

    async def _load_whisper(self):
        """Load faster-whisper model (runs on CPU or CUDA)."""
        if self._whisper_model:
            return

        try:
            from faster_whisper import WhisperModel

            # Use CPU for real-time (tiny/base models are fast enough)
            # Use int8 quantization for speed
            device = "cpu"
            compute_type = "int8"

            try:
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
                    compute_type = "float16"
            except ImportError:
                pass

            self._whisper_model = await asyncio.to_thread(
                WhisperModel,
                self._model_size,
                device=device,
                compute_type=compute_type,
            )
            logger.info(f"Whisper model loaded: {self._model_size} on {device}")
        except ImportError:
            logger.error(
                "faster-whisper not installed. Install with: pip install faster-whisper\n"
                "Falling back to caption scraping."
            )
            raise

    async def _transcribe_whisper(self, audio_data: bytes) -> tuple[str, float]:
        """Transcribe audio using faster-whisper (local)."""
        if not self._whisper_model:
            await self._load_whisper()

        # Convert PCM16 bytes to float32 numpy array
        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

        # Run transcription in thread pool to not block event loop
        def _transcribe():
            segments, info = self._whisper_model.transcribe(
                samples,
                language=self._language,
                beam_size=1,          # Fastest decoding
                best_of=1,
                vad_filter=False,     # Disabled -- our own VAD handles boundaries
            )
            texts = []
            confidences = []
            for seg in segments:
                texts.append(seg.text)
                # faster-whisper >= 1.1 uses avg_logprob, older uses avg_log_prob
                log_prob = getattr(seg, 'avg_logprob', None) or getattr(seg, 'avg_log_prob', -1.0)
                confidences.append(log_prob)

            full_text = " ".join(texts).strip()
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            # Convert log prob to 0-1 scale (rough approximation)
            confidence = min(max(1.0 + avg_confidence / 2.0, 0.0), 1.0)
            return full_text, confidence

        return await asyncio.to_thread(_transcribe)

    async def _transcribe_deepgram(self, audio_data: bytes) -> tuple[str, float]:
        """Transcribe audio using Deepgram cloud API (lowest latency)."""
        import httpx
        from gneva.config import get_settings
        settings = get_settings()

        dg_key = getattr(settings, 'deepgram_api_key', '')
        if not dg_key:
            raise RuntimeError("deepgram_api_key not configured")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.deepgram.com/v1/listen",
                params={
                    "model": "nova-2",
                    "language": self._language,
                    "smart_format": "true",
                    "encoding": "linear16",
                    "sample_rate": str(SAMPLE_RATE),
                    "channels": "1",
                },
                headers={
                    "Authorization": f"Token {dg_key}",
                    "Content-Type": "application/octet-stream",
                },
                content=audio_data,
                timeout=5,
            )

            if resp.status_code != 200:
                raise RuntimeError(f"Deepgram error: {resp.status_code}")

            data = resp.json()
            alt = data.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0]
            text = alt.get("transcript", "")
            confidence = alt.get("confidence", 0.0)
            return text, confidence

    def get_stats(self) -> dict:
        track_info = {}
        for tid, tb in self._track_buffers.items():
            track_info[tid] = {
                "buffer_sec": round(len(tb.audio_buffer) / (SAMPLE_RATE * 2), 2),
                "is_speaking": tb.is_speaking,
            }

        return {
            "backend": self._backend,
            "model_size": self._model_size,
            "running": self._running,
            "total_utterances": self._total_utterances,
            "total_audio_sec": round(self._total_audio_sec, 1),
            "active_tracks": len(self._track_buffers),
            "tracks": track_info,
        }
