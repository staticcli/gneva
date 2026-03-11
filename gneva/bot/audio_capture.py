"""Audio capture server — receives PCM from injected JS via WebSocket, writes WAV."""

import asyncio
import struct
import wave
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

AUDIO_JS_PATH = Path(__file__).parent / "audio_capture.js"


class AudioCapture:
    """WebSocket server that receives PCM16 audio chunks and writes them to a WAV file."""

    def __init__(self, output_path: str, sample_rate: int = 16000):
        self.output_path = output_path
        self.sample_rate = sample_rate
        self.channels = 1
        self._server = None
        self._port = 0
        self._chunks: list[bytes] = []
        self._total_bytes = 0
        self._running = False

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

    async def _handle_connection(self, websocket):
        """Handle incoming WebSocket connection from injected JS."""
        logger.info("Audio capture: browser connected")
        try:
            async for message in websocket:
                if isinstance(message, bytes) and self._running:
                    self._chunks.append(message)
                    self._total_bytes += len(message)
        except Exception as e:
            logger.debug(f"Audio WS connection closed: {e}")

    async def stop(self) -> str:
        """Stop capture, write WAV file, return the file path."""
        self._running = False

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # Write WAV
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
        logger.info(
            f"Audio saved: {self.output_path} "
            f"({duration_sec:.1f}s, {self._total_bytes / 1024:.0f} KB)"
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
