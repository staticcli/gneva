"""Entity extraction from transcripts using Claude Haiku."""

import json
import logging
from dataclasses import dataclass, field

from gneva.config import get_settings
from gneva.services import get_anthropic_client

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = """You are an expert at extracting structured knowledge from meeting transcripts.
Extract all entities with precision. Do not hallucinate entities not explicitly
mentioned. When uncertain, lower the confidence score rather than omitting.

Always use the extract_entities tool to return structured output."""

EXTRACT_TOOL = {
    "name": "extract_entities",
    "description": "Extract all entities from the meeting transcript chunk",
    "input_schema": {
        "type": "object",
        "properties": {
            "people": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                        "organization": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["name", "confidence"],
                },
            },
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "statement": {"type": "string"},
                        "rationale": {"type": "string"},
                        "owner": {"type": "string"},
                        "confidence": {"type": "number"},
                        "evidence_quote": {"type": "string"},
                    },
                    "required": ["statement", "confidence"],
                },
            },
            "action_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "assignee": {"type": "string"},
                        "due_date": {"type": "string"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                        "confidence": {"type": "number"},
                    },
                    "required": ["description", "confidence"],
                },
            },
            "projects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "status": {"type": "string"},
                        "owner": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["name", "confidence"],
                },
            },
            "topics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "sentiment": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["name", "confidence"],
                },
            },
        },
    },
}


@dataclass
class ExtractionResult:
    people: list[dict] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    action_items: list[dict] = field(default_factory=list)
    projects: list[dict] = field(default_factory=list)
    topics: list[dict] = field(default_factory=list)


def extract_entities(transcript_text: str, chunk_size: int = 4000, overlap: int = 400) -> ExtractionResult:
    """Extract entities from a transcript using Claude Haiku.

    Processes transcript in chunks with overlap to avoid missing entities at boundaries.
    Returns empty ExtractionResult if the Anthropic client is unavailable.
    """
    try:
        client = get_anthropic_client()
    except RuntimeError as e:
        logger.warning("Skipping entity extraction: %s", e)
        return ExtractionResult()
    result = ExtractionResult()

    # Split into chunks
    words = transcript_text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap

    logger.info(f"Processing {len(chunks)} chunks for entity extraction")

    for idx, chunk in enumerate(chunks):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=[EXTRACT_TOOL],
                tool_choice={"type": "tool", "name": "extract_entities"},
                messages=[{"role": "user", "content": f"Extract entities from this meeting transcript chunk ({idx + 1}/{len(chunks)}):\n\n{chunk}"}],
            )

            # Parse tool use response
            for block in response.content:
                if block.type == "tool_use":
                    data = block.input
                    result.people.extend(data.get("people", []))
                    result.decisions.extend(data.get("decisions", []))
                    result.action_items.extend(data.get("action_items", []))
                    result.projects.extend(data.get("projects", []))
                    result.topics.extend(data.get("topics", []))

        except Exception as e:
            logger.error(f"Extraction failed for chunk {idx}: {e}")

    logger.info(
        f"Extracted: {len(result.people)} people, {len(result.decisions)} decisions, "
        f"{len(result.action_items)} action items, {len(result.projects)} projects, "
        f"{len(result.topics)} topics"
    )

    return result
