"""TalkingHeadService — wraps SadTalker for generating talking head video from face + audio.

Provides voice-to-face mapping and graceful degradation when SadTalker is not installed.
If SadTalker is unavailable, callers fall back to canvas-based avatar animation.
"""

import base64
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Directory containing face images
FACES_DIR = Path(__file__).parent / "faces"

# Voice ID → face image filename mapping
VOICE_FACE_MAP: dict[str, str] = {
    "OUBnvvuqEKdDWtapoJFn": "patel.jpg",    # Patel — Indian accent (default)
    "56bWURjYFHyYyVf490Dp": "emma.jpg",      # Emma — warm, friendly
    "EXAVITQu4vr4xnSDxMaL": "emma.jpg",     # Sarah — fallback to Emma
}

# SadTalker checkpoint directory (configurable via env)
SADTALKER_CHECKPOINT_DIR = os.environ.get(
    "SADTALKER_CHECKPOINT_DIR",
    "/opt/sadtalker/checkpoints",
)


_singleton_instance = None


def get_talking_head_service() -> "TalkingHeadService":
    """A2 fix: Return singleton TalkingHeadService to avoid re-scanning on each bot launch."""
    global _singleton_instance
    if _singleton_instance is None:
        _singleton_instance = TalkingHeadService()
    return _singleton_instance


class TalkingHeadService:
    """Generates talking head video frames from a face image and audio.

    Uses SadTalker when available; gracefully degrades to empty output
    so callers can fall back to canvas-based animation.
    """

    def __init__(self):
        self._sadtalker_available: bool | None = None
        self._sadtalker_model = None
        self._face_images: dict[str, Path] = {}

        # Discover available face images
        self._load_face_images()

    def _load_face_images(self) -> None:
        """Scan the faces directory and register available images."""
        if not FACES_DIR.is_dir():
            logger.warning("Faces directory not found: %s", FACES_DIR)
            return

        for path in FACES_DIR.iterdir():
            if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                self._face_images[path.stem] = path

        if self._face_images:
            logger.info(
                "Loaded %d face images: %s",
                len(self._face_images),
                list(self._face_images.keys()),
            )
        else:
            logger.warning("No face images found in %s", FACES_DIR)

    def is_available(self) -> bool:
        """Check if SadTalker models are loaded and ready for inference."""
        if self._sadtalker_available is None:
            self._sadtalker_available = self._check_sadtalker()
        return self._sadtalker_available

    def _check_sadtalker(self) -> bool:
        """Probe whether SadTalker can be imported and checkpoints exist."""
        try:
            checkpoint_path = Path(SADTALKER_CHECKPOINT_DIR)
            if not checkpoint_path.is_dir():
                logger.info(
                    "SadTalker checkpoints not found at %s — disabled",
                    SADTALKER_CHECKPOINT_DIR,
                )
                return False

            # Attempt lazy import to verify installation
            from src.generate_batch import get_data  # noqa: F401
            from src.generate_facerender import (  # noqa: F401
                generate_batch,
                init_facerender,
            )

            logger.info("SadTalker is available (checkpoints: %s)", SADTALKER_CHECKPOINT_DIR)
            return True
        except ImportError:
            logger.info("SadTalker not installed — talking head generation disabled")
            return False
        except Exception as e:
            logger.warning("SadTalker check failed: %s", e)
            return False

    def _ensure_sadtalker_loaded(self) -> bool:
        """Lazy-load the SadTalker model on first use."""
        if not self.is_available():
            return False

        if self._sadtalker_model is not None:
            return True

        try:
            from src.generate_facerender import init_facerender

            self._sadtalker_model = init_facerender(
                checkpoint_dir=SADTALKER_CHECKPOINT_DIR,
            )
            logger.info("SadTalker model loaded successfully")
            return True
        except Exception as e:
            logger.error("Failed to load SadTalker model: %s", e, exc_info=True)
            self._sadtalker_available = False
            return False

    def get_face_image(self, voice_id: str | None = None) -> Path | None:
        """Return the face image path for a voice ID.

        Falls back to the first available face image if the voice ID
        is not mapped or its image file is missing.

        Returns None if no face images are available at all.
        """
        # Try the mapped filename for this voice
        if voice_id and voice_id in VOICE_FACE_MAP:
            filename = VOICE_FACE_MAP[voice_id]
            face_path = FACES_DIR / filename
            if face_path.is_file():
                return face_path
            logger.warning(
                "Mapped face image not found for voice %s: %s",
                voice_id,
                face_path,
            )

        # Fall back to first available image
        if self._face_images:
            first_path = next(iter(self._face_images.values()))
            logger.debug(
                "Using fallback face image for voice_id=%s: %s",
                voice_id,
                first_path.name,
            )
            return first_path

        return None

    def get_face_b64(self, voice_id: str | None = None) -> str | None:
        """Return the face image as a base64-encoded PNG string.

        Used for injecting a static photo avatar into the browser canvas.
        Returns None if no face image is available.
        """
        face_path = self.get_face_image(voice_id)
        if face_path is None:
            return None

        try:
            image_bytes = face_path.read_bytes()
            b64 = base64.b64encode(image_bytes).decode("ascii")

            # Determine MIME type from extension
            ext = face_path.suffix.lower()
            mime_map = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
            }
            mime = mime_map.get(ext, "image/png")

            return f"data:{mime};base64,{b64}"
        except Exception as e:
            logger.error("Failed to encode face image %s: %s", face_path, e)
            return None

    def generate_talking_frames(
        self,
        face_image_path: str | Path,
        audio_bytes: bytes,
    ) -> list[bytes]:
        """Generate talking head video frames from a face image and audio.

        Args:
            face_image_path: Path to the source face image (PNG/JPG).
            audio_bytes: Raw audio bytes (WAV format expected).

        Returns:
            List of PNG frame bytes. Empty list if SadTalker is unavailable
            or inference fails (caller should fall back to canvas animation).
        """
        if not self._ensure_sadtalker_loaded():
            return []

        try:
            from src.generate_batch import get_data
            from src.generate_facerender import generate_batch

            face_image_path = Path(face_image_path)
            if not face_image_path.is_file():
                logger.error("Face image not found: %s", face_image_path)
                return []

            # Write audio to a temp file for SadTalker
            with tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False
            ) as tmp_audio:
                tmp_audio.write(audio_bytes)
                tmp_audio_path = tmp_audio.name

            try:
                # Prepare input data for SadTalker
                data = get_data(
                    first_frame_dir=None,
                    driving_audio_path=tmp_audio_path,
                    source_image_path=str(face_image_path),
                )

                # Run face rendering inference
                result = generate_batch(
                    self._sadtalker_model,
                    data,
                    checkpoint_dir=SADTALKER_CHECKPOINT_DIR,
                )

                # Extract frames as PNG bytes
                frames: list[bytes] = []
                if result and hasattr(result, "__iter__"):
                    import io

                    from PIL import Image

                    for frame_array in result:
                        img = Image.fromarray(frame_array)
                        buf = io.BytesIO()
                        img.save(buf, format="PNG")
                        frames.append(buf.getvalue())

                logger.info(
                    "Generated %d talking head frames from %s",
                    len(frames),
                    face_image_path.name,
                )
                return frames

            finally:
                # Clean up temp audio file
                try:
                    os.unlink(tmp_audio_path)
                except OSError:
                    pass

        except Exception as e:
            logger.error(
                "SadTalker inference failed: %s", e, exc_info=True
            )
            # Mark as unavailable to avoid repeated failures
            self._sadtalker_available = False
            return []
