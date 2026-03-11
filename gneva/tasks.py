"""Pipeline task entry point — delegates to async runner (no Celery required)."""

import asyncio
import logging

logger = logging.getLogger(__name__)


def process_meeting_sync(meeting_id: str):
    """Synchronous wrapper for the async pipeline — use for CLI or background threads."""
    from gneva.pipeline.runner import process_meeting
    asyncio.run(process_meeting(meeting_id))


# Re-export for convenience
from gneva.pipeline.runner import process_meeting  # noqa: F401, E402
