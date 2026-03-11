"""Shared service utilities."""

import anthropic
from gneva.config import get_settings

_client = None


def get_anthropic_client():
    """Return a lazily-initialized shared Anthropic client singleton.

    Raises RuntimeError if the Anthropic API key is not configured.
    """
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "Anthropic API key not configured. Set ANTHROPIC_API_KEY in your environment."
            )
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client
