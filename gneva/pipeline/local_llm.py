"""Local LLM fallback using Ollama for entity extraction and summarization."""

import json
import logging

import httpx

from gneva.config import get_settings

logger = logging.getLogger(__name__)

EXTRACTION_EXAMPLE = """{
  "people": [{"name": "...", "role": "...", "confidence": 0.9}],
  "projects": [{"name": "...", "status": "...", "confidence": 0.9}],
  "topics": [{"name": "...", "confidence": 0.9}],
  "decisions": [{"statement": "...", "rationale": "...", "confidence": 0.9}],
  "action_items": [{"description": "...", "priority": "medium", "confidence": 0.9}]
}"""

SUMMARY_EXAMPLE = """{
  "tldr": "2-3 sentence summary",
  "key_decisions": ["decision 1", "decision 2"],
  "action_items": [{"task": "...", "owner": "...", "due_date": ""}],
  "topics_covered": ["topic 1", "topic 2"],
  "sentiment": "neutral",
  "follow_up_needed": false
}"""


async def _call_ollama(prompt: str, system: str = "") -> str:
    """Send a prompt to Ollama and return the response text."""
    settings = get_settings()

    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
    }
    if system:
        payload["system"] = system

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.ollama_url}/api/generate",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
    except httpx.ConnectError:
        logger.warning("Ollama not running — cannot process with local LLM")
        return ""
    except Exception as e:
        logger.error(f"Ollama request failed: {e}")
        return ""


def _parse_json(raw: str) -> dict | None:
    """Extract JSON from LLM response."""
    if not raw:
        return None
    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Try extracting JSON block
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass
    return None


async def extract_entities_local(transcript_text: str) -> dict:
    """Extract entities from transcript using local Ollama model."""
    system = (
        "You are an expert at extracting structured knowledge from meeting transcripts. "
        "Extract all people, projects, topics, decisions, and action items. "
        "Return ONLY valid JSON, no other text."
    )
    prompt = (
        f"Extract entities from this meeting transcript. "
        f"Return JSON with this exact structure:\n{EXTRACTION_EXAMPLE}\n\n"
        f"Transcript:\n{transcript_text[:8000]}"
    )

    raw = await _call_ollama(prompt, system)
    result = _parse_json(raw)
    if result:
        return result

    return {"people": [], "projects": [], "topics": [], "decisions": [], "action_items": []}


async def summarize_local(transcript_text: str, entities_ctx: str) -> dict:
    """Generate meeting summary using local Ollama model."""
    system = (
        "You are Gneva, an AI that generates concise meeting summaries. "
        "Return ONLY valid JSON, no other text."
    )
    prompt = (
        f"Summarize this meeting transcript. "
        f"Return JSON with this exact structure:\n{SUMMARY_EXAMPLE}\n\n"
    )
    if entities_ctx:
        prompt += f"Extracted entities:\n{entities_ctx}\n\n"
    prompt += f"Transcript:\n{transcript_text[:12000]}"

    raw = await _call_ollama(prompt, system)
    result = _parse_json(raw)
    if result and "tldr" in result:
        return result

    return {
        "tldr": "Summary generation failed — no LLM available.",
        "key_decisions": [],
        "action_items": [],
        "topics_covered": [],
        "sentiment": "neutral",
        "follow_up_needed": False,
    }
