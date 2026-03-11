"""Text-to-speech service — Piper (local) and ElevenLabs (cloud) backends."""

import io
import logging
import subprocess
import tempfile
from pathlib import Path

import httpx

from gneva.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

ELEVENLABS_API = "https://api.elevenlabs.io/v1"


class TTSService:
    """Synthesize speech from text using Piper or ElevenLabs."""

    def __init__(self):
        self._backend = settings.tts_backend  # "piper" or "elevenlabs"
        self._piper_model = settings.piper_model_path
        self._el_key = settings.elevenlabs_api_key
        self._el_voice = settings.elevenlabs_voice_id

    async def synthesize(self, text: str, voice: str = "gneva") -> bytes:
        """Synthesize text to WAV audio bytes.

        Args:
            text: The text to speak.
            voice: Voice identifier (used by ElevenLabs; Piper uses model path).

        Returns:
            Raw WAV audio bytes.
        """
        if not text or not text.strip():
            raise ValueError("Cannot synthesize empty text")

        # Strip null bytes and enforce length limit
        text = text.replace("\x00", "")
        if len(text) > 5000:
            raise ValueError("Text exceeds maximum length of 5000 characters")

        if self._backend == "elevenlabs":
            return await self._synthesize_elevenlabs(text, voice)
        return await self._synthesize_piper(text)

    async def _synthesize_piper(self, text: str) -> bytes:
        """Synthesize using local Piper TTS (subprocess call)."""
        if not self._piper_model:
            raise RuntimeError("piper_model_path not configured")

        model_path = Path(self._piper_model)
        if not model_path.exists():
            raise FileNotFoundError(f"Piper model not found: {model_path}")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out_path = tmp.name

        try:
            proc = subprocess.run(
                [
                    "piper",
                    "--model", str(model_path),
                    "--output_file", out_path,
                ],
                input=text,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode != 0:
                logger.error("Piper stderr: %s", proc.stderr)
                raise RuntimeError(f"Piper failed (exit {proc.returncode}): {proc.stderr[:200]}")

            with open(out_path, "rb") as f:
                return f.read()
        finally:
            Path(out_path).unlink(missing_ok=True)

    async def _synthesize_elevenlabs(self, text: str, voice: str = "gneva") -> bytes:
        """Synthesize using ElevenLabs cloud API."""
        if not self._el_key:
            raise RuntimeError("elevenlabs_api_key not configured")

        voice_id = self._el_voice
        if not voice_id:
            raise RuntimeError("elevenlabs_voice_id not configured")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{ELEVENLABS_API}/text-to-speech/{voice_id}",
                headers={
                    "xi-api-key": self._el_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/wav",
                },
                json={
                    "text": text,
                    "model_id": "eleven_turbo_v2_5",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                        "style": 0.0,
                        "use_speaker_boost": True,
                    },
                },
                timeout=30,
            )
            if resp.status_code != 200:
                logger.error("ElevenLabs error %d: %s", resp.status_code, resp.text[:200])
                raise RuntimeError(f"ElevenLabs API error: {resp.status_code}")
            return resp.content

    async def get_available_voices(self) -> list[dict]:
        """List available voices for the active backend."""
        if self._backend == "elevenlabs":
            return await self._list_elevenlabs_voices()
        return self._list_piper_voices()

    async def _list_elevenlabs_voices(self) -> list[dict]:
        if not self._el_key:
            return []
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{ELEVENLABS_API}/voices",
                headers={"xi-api-key": self._el_key},
                timeout=10,
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            return [
                {
                    "id": v["voice_id"],
                    "name": v["name"],
                    "category": v.get("category", "unknown"),
                    "preview_url": v.get("preview_url"),
                }
                for v in data.get("voices", [])
            ]

    def _list_piper_voices(self) -> list[dict]:
        """List locally available Piper models."""
        if not self._piper_model:
            return []
        model_dir = Path(self._piper_model).parent
        voices = []
        for onnx in model_dir.glob("*.onnx"):
            voices.append({
                "id": onnx.stem,
                "name": onnx.stem.replace("-", " ").replace("_", " ").title(),
                "category": "local",
                "path": str(onnx),
            })
        return voices
