"""System audio capture via WASAPI loopback — captures what plays through speakers.

This bypasses the browser WebSocket audio pipeline entirely. Instead of intercepting
WebRTC tracks via injected JS, we capture the actual audio output of the system.

Flow: Meeting audio → Speakers → WASAPI loopback → PCM16 @ 16kHz → RealtimeSTT

Requires: pip install PyAudioWPatch
"""

import asyncio
import logging
import struct
import numpy as np
from typing import Callable

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16000
CHUNK_DURATION_MS = 100  # Send chunks every 100ms


class SystemAudioCapture:
    """Captures system audio output via WASAPI loopback and feeds it to a callback."""

    def __init__(self, on_audio_chunk: Callable[[bytes], None] | None = None):
        """
        Args:
            on_audio_chunk: Callback receiving PCM16 mono 16kHz bytes.
        """
        self._on_audio_chunk = on_audio_chunk
        self._running = False
        self._stream = None
        self._pa = None
        self._capture_task: asyncio.Task | None = None

        # Source device info (filled on start)
        self._source_rate = 44100
        self._source_channels = 2
        self._device_index = -1

    async def start(self):
        """Start capturing system audio in a background thread."""
        import pyaudiowpatch as pyaudio

        self._pa = pyaudio.PyAudio()

        try:
            loopback = self._pa.get_default_wasapi_loopback()
            self._device_index = loopback["index"]
            self._source_rate = int(loopback["defaultSampleRate"])
            self._source_channels = loopback["maxInputChannels"]
            logger.info(
                f"System audio: using '{loopback['name']}' "
                f"({self._source_channels}ch @ {self._source_rate}Hz)"
            )
        except Exception as e:
            logger.error(f"No WASAPI loopback device found: {e}")
            self._pa.terminate()
            self._pa = None
            raise RuntimeError(f"No loopback device: {e}")

        self._running = True
        self._capture_task = asyncio.create_task(
            asyncio.to_thread(self._capture_loop)
        )

    def _capture_loop(self):
        """Blocking capture loop — runs in a thread."""
        import pyaudiowpatch as pyaudio

        # Calculate chunk size for ~100ms of audio at source rate
        chunk_frames = int(self._source_rate * CHUNK_DURATION_MS / 1000)

        try:
            self._stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=self._source_channels,
                rate=self._source_rate,
                input=True,
                input_device_index=self._device_index,
                frames_per_buffer=chunk_frames,
            )

            logger.info("System audio capture started")

            while self._running:
                try:
                    data = self._stream.read(chunk_frames, exception_on_overflow=False)
                except Exception as e:
                    if self._running:
                        logger.debug(f"Audio read error: {e}")
                    continue

                if not data or not self._on_audio_chunk:
                    continue

                # Convert: source format → PCM16 mono 16kHz
                pcm_mono_16k = self._resample(data)

                if pcm_mono_16k and len(pcm_mono_16k) > 0:
                    try:
                        self._on_audio_chunk(pcm_mono_16k)
                    except Exception:
                        pass

        except Exception as e:
            if self._running:
                logger.error(f"System audio capture error: {e}")
        finally:
            if self._stream:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except Exception:
                    pass

    def _resample(self, raw_bytes: bytes) -> bytes:
        """Convert raw audio to PCM16 mono 16kHz."""
        # Parse as int16 samples
        samples = np.frombuffer(raw_bytes, dtype=np.int16)

        # Stereo → mono (average channels)
        if self._source_channels >= 2:
            samples = samples.reshape(-1, self._source_channels)
            samples = samples.mean(axis=1).astype(np.int16)

        # Resample if needed (e.g., 44100 → 16000)
        if self._source_rate != TARGET_SAMPLE_RATE:
            # Simple linear interpolation resample
            duration = len(samples) / self._source_rate
            target_len = int(duration * TARGET_SAMPLE_RATE)
            if target_len == 0:
                return b""
            indices = np.linspace(0, len(samples) - 1, target_len)
            samples = np.interp(indices, np.arange(len(samples)), samples.astype(np.float32))
            samples = samples.astype(np.int16)

        return samples.tobytes()

    async def stop(self):
        """Stop capturing."""
        self._running = False

        if self._capture_task and not self._capture_task.done():
            try:
                await asyncio.wait_for(self._capture_task, timeout=3)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._capture_task.cancel()

        if self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

        logger.info("System audio capture stopped")
