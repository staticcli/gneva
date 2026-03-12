"""Audio capture server — receives per-track PCM from injected JS via WebSocket, writes WAV."""

import asyncio
import struct
import wave
import logging
import os
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

AUDIO_JS_PATH = Path(__file__).parent / "audio_capture.js"

# Track ID 0 is the fallback mixed-audio path (DOM element capture)
FALLBACK_TRACK_ID = 0


class AudioCapture:
    """WebSocket server that receives per-track PCM16 audio chunks and writes them to WAV files.

    Each incoming WebSocket message has a 4-byte big-endian track ID header followed
    by PCM16 audio data. Tracks are kept separate so each speaker can be transcribed
    independently.
    """

    def __init__(self, output_path: str, sample_rate: int = 16000):
        self.output_path = output_path
        self.sample_rate = sample_rate
        self.channels = 1
        self._server = None
        self._port = 0
        # Per-track audio storage: track_id -> list[bytes]
        self._track_chunks: dict[int, list[bytes]] = {}
        # Combined chunks for WAV output (all tracks mixed)
        self._chunks: list[bytes] = []
        self._total_bytes = 0
        self._running = False
        # Callback for real-time STT — receives (pcm_bytes, track_id)
        self._on_audio_chunk: Callable[[bytes, int], None] | None = None
        # Legacy callback without track_id (for backward compat)
        self._on_audio_chunk_legacy: Callable[[bytes], None] | None = None

    @property
    def port(self) -> int:
        return self._port

    def get_ws_url(self) -> str:
        return f"ws://127.0.0.1:{self._port}"

    def get_inject_js(self) -> str:
        """Return the audio capture JS with the WebSocket URL injected."""
        js = AUDIO_JS_PATH.read_text(encoding="utf-8")
        return js.replace("__WS_URL__", self.get_ws_url())

    async def start(self):
        """Start the WebSocket server on a random available port."""
        import websockets

        self._running = True
        self._server = await websockets.serve(
            self._handle_connection,
            "127.0.0.1",
            0,  # random port
        )
        # Get the actual port
        for sock in self._server.sockets:
            addr = sock.getsockname()
            self._port = addr[1]
            break

        logger.info(f"Audio capture WebSocket started on port {self._port}")

    def set_audio_chunk_callback(self, callback: Callable[[bytes, int], None]):
        """Set a callback to receive raw PCM chunks with track ID (for per-speaker STT).

        Callback signature: callback(pcm_bytes: bytes, track_id: int)
        """
        self._on_audio_chunk = callback

    def set_legacy_audio_chunk_callback(self, callback: Callable[[bytes], None]):
        """Set a legacy callback that receives raw PCM chunks without track ID."""
        self._on_audio_chunk_legacy = callback

    async def _handle_connection(self, websocket):
        """Handle incoming WebSocket connection from injected JS.

        Each binary message has format: [4-byte uint32 BE track_id][PCM16 audio data]
        """
        logger.info("Audio capture: browser connected")
        msg_count = 0
        tracks_seen = set()

        try:
            async for message in websocket:
                if not isinstance(message, bytes) or not self._running:
                    continue

                msg_count += 1

                # Parse track ID header (4 bytes big-endian uint32)
                if len(message) <= 4:
                    continue

                track_id = struct.unpack('>I', message[:4])[0]
                pcm_data = message[4:]

                # Log first message from each track
                if track_id not in tracks_seen:
                    tracks_seen.add(track_id)
                    logger.info(
                        f"Audio capture: first data from track {track_id} "
                        f"({len(pcm_data)} bytes, total tracks: {len(tracks_seen)})"
                    )

                # Store per-track
                if track_id not in self._track_chunks:
                    self._track_chunks[track_id] = []
                self._track_chunks[track_id].append(pcm_data)

                # Also store combined for WAV output
                self._chunks.append(pcm_data)
                self._total_bytes += len(pcm_data)

                # Forward to real-time STT with track ID
                if self._on_audio_chunk:
                    try:
                        self._on_audio_chunk(pcm_data, track_id)
                    except Exception:
                        pass
                elif self._on_audio_chunk_legacy:
                    try:
                        self._on_audio_chunk_legacy(pcm_data)
                    except Exception:
                        pass

                # Periodic logging
                if msg_count % 500 == 0:
                    logger.debug(
                        f"Audio capture: {msg_count} messages, "
                        f"{self._total_bytes / 1024:.0f} KB, "
                        f"{len(tracks_seen)} tracks"
                    )

        except Exception as e:
            logger.debug(f"Audio WS connection closed: {e}")

        logger.info(
            f"Audio capture: connection ended — "
            f"{msg_count} messages, {len(tracks_seen)} tracks, "
            f"{self._total_bytes / 1024:.0f} KB total"
        )

    def get_track_ids(self) -> list[int]:
        """Return list of track IDs that have received audio."""
        return list(self._track_chunks.keys())

    async def stop(self) -> str:
        """Stop capture, write WAV file, return the file path."""
        self._running = False

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # Write combined WAV (all tracks mixed together)
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

        if not self._chunks:
            logger.warning("No audio data captured")
            return self.output_path

        with wave.open(self.output_path, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit = 2 bytes
            wf.setframerate(self.sample_rate)
            for chunk in self._chunks:
                wf.writeframes(chunk)

        duration_sec = self._total_bytes / (self.sample_rate * 2 * self.channels)
        track_summary = ", ".join(
            f"track{tid}={len(chunks)}chunks"
            for tid, chunks in self._track_chunks.items()
        )
        logger.info(
            f"Audio saved: {self.output_path} "
            f"({duration_sec:.1f}s, {self._total_bytes / 1024:.0f} KB, "
            f"tracks: {track_summary})"
        )
        return self.output_path

    @property
    def duration_sec(self) -> float:
        if not self._total_bytes:
            return 0.0
        return self._total_bytes / (self.sample_rate * 2 * self.channels)

    @property
    def has_audio(self) -> bool:
        return self._total_bytes > 0
