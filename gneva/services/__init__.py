"""Shared service utilities."""

import asyncio
import functools
import logging

import anthropic
from gneva.config import get_settings

logger = logging.getLogger(__name__)

_client = None

# Concurrency limiter for LLM calls — prevents flooding the Anthropic API
# when multiple agents make parallel requests (deliberation, broadcast, etc.).
# Default: 5 concurrent requests. Override via LLM_MAX_CONCURRENCY env var.
_llm_semaphore: asyncio.Semaphore | None = None


def _get_llm_semaphore() -> asyncio.Semaphore:
    """Lazily create the LLM concurrency semaphore (must be called in an async context)."""
    global _llm_semaphore
    if _llm_semaphore is None:
        settings = get_settings()
        max_concurrent = int(getattr(settings, "llm_max_concurrency", 5) or 5)
        _llm_semaphore = asyncio.Semaphore(max_concurrent)
    return _llm_semaphore


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


async def llm_create(**kwargs) -> "anthropic.types.Message":
    """Concurrency-limited LLM call. Drop-in replacement for client.messages.create.

    Usage:
        from gneva.services import llm_create
        response = await llm_create(model="claude-sonnet-4-6", max_tokens=300,
                                     system="...", messages=[...])
    """
    sem = _get_llm_semaphore()
    client = get_anthropic_client()
    async with sem:
        return await asyncio.to_thread(client.messages.create, **kwargs)


async def llm_analyze(prompt: str, system: str, model: str = "claude-haiku-4-5-20251001",
                      max_tokens: int = 300) -> str:
    """Shared LLM analysis helper used by agent tools and specialist tools."""
    response = await llm_create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip() if response.content else "No analysis generated."


def retry_transient(max_retries: int = 2, base_delay: float = 1.0):
    """Decorator that retries async functions on transient API errors.

    Retries on timeouts, rate limits (429), and server errors (500+).
    Uses exponential backoff: base_delay * 2^attempt (1s, 2s).
    No new dependencies required.
    """
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return await fn(*args, **kwargs)
                except Exception as exc:
                    if not _is_transient(exc) or attempt >= max_retries:
                        raise
                    last_exc = exc
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"Transient error in {fn.__name__} (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {delay}s: {exc}"
                    )
                    await asyncio.sleep(delay)
            raise last_exc  # should not reach here
        return wrapper
    return decorator


def _is_transient(exc: Exception) -> bool:
    """Check if an exception is a transient/retryable error."""
    # Anthropic SDK specific errors
    if isinstance(exc, anthropic.RateLimitError):
        return True
    if isinstance(exc, anthropic.InternalServerError):
        return True
    if isinstance(exc, anthropic.APITimeoutError):
        return True
    if isinstance(exc, anthropic.APIConnectionError):
        return True
    # Generic status code check for HTTP errors
    status = getattr(exc, "status_code", None)
    if status is not None:
        if status == 429 or status >= 500:
            return True
    # Timeout errors
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError)):
        return True
    return False
