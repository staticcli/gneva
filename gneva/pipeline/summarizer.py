"""Meeting summary generation using Claude Sonnet."""

import logging
from dataclasses import dataclass

from gneva.config import get_settings
from gneva.services import get_anthropic_client

logger = logging.getLogger(__name__)
settings = get_settings()

SUMMARY_SYSTEM = """You are Gneva, an AI team member that generates concise, actionable meeting summaries.

Given a meeting transcript and extracted entities, produce:
1. A TL;DR (2-3 sentences max)
2. Key decisions made (bullet list)
3. Action items with owners and due dates
4. Topics covered
5. Meeting sentiment (positive, neutral, tense, productive)
6. Whether a follow-up meeting is needed (true/false)

Be precise. Do not add information not present in the transcript.
Use the generate_summary tool to return structured output."""

SUMMARY_TOOL = {
    "name": "generate_summary",
    "description": "Generate a structured meeting summary",
    "input_schema": {
        "type": "object",
        "properties": {
            "tldr": {"type": "string", "description": "2-3 sentence summary"},
            "key_decisions": {"type": "array", "items": {"type": "string"}},
            "action_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string"},
                        "owner": {"type": "string"},
                        "due_date": {"type": "string"},
                    },
                },
            },
            "topics_covered": {"type": "array", "items": {"type": "string"}},
            "sentiment": {"type": "string", "enum": ["positive", "neutral", "tense", "productive"]},
            "follow_up_needed": {"type": "boolean"},
        },
        "required": ["tldr", "key_decisions", "action_items", "topics_covered", "sentiment", "follow_up_needed"],
    },
}


@dataclass
class SummaryResult:
    tldr: str
    key_decisions: list[str]
    action_items: list[dict]
    topics_covered: list[str]
    sentiment: str
    follow_up_needed: bool


def generate_summary(transcript_text: str, entities_context: str = "") -> SummaryResult:
    """Generate a meeting summary using Claude Sonnet.

    Raises RuntimeError if the Anthropic client is unavailable.
    """
    client = get_anthropic_client()  # raises RuntimeError if key not set

    user_msg = f"Meeting transcript:\n\n{transcript_text[:15000]}"
    if entities_context:
        user_msg += f"\n\nExtracted entities:\n{entities_context}"

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=SUMMARY_SYSTEM,
        tools=[SUMMARY_TOOL],
        tool_choice={"type": "tool", "name": "generate_summary"},
        messages=[{"role": "user", "content": user_msg}],
    )

    for block in response.content:
        if block.type == "tool_use":
            data = block.input
            return SummaryResult(
                tldr=data["tldr"],
                key_decisions=data["key_decisions"],
                action_items=data["action_items"],
                topics_covered=data["topics_covered"],
                sentiment=data["sentiment"],
                follow_up_needed=data["follow_up_needed"],
            )

    raise RuntimeError("Claude did not return summary tool use")
