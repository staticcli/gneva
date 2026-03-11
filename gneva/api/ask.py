"""Freeform Q&A endpoint — ask Gneva anything about your org."""

import asyncio

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.db import get_db
from gneva.models.user import User
from gneva.models.entity import Entity
from gneva.models.meeting import MeetingSummary, TranscriptSegment
from gneva.auth import get_current_user
from gneva.config import get_settings

router = APIRouter(prefix="/api/ask", tags=["ask"])
settings = get_settings()


def _escape_like(s: str) -> str:
    return s.replace("%", r"\%").replace("_", r"\_")


class AskRequest(BaseModel):
    question: str
    max_sources: int = 5


@router.post("")
async def ask_gneva(
    req: AskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """RAG-grounded answer from organizational memory."""
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=503, detail="Anthropic API not configured")

    # Phase 1: keyword retrieval (semantic retrieval added when embedder is ready)
    entities = (await db.execute(
        select(Entity)
        .where(Entity.org_id == user.org_id)
        .where(or_(
            Entity.name.ilike(f"%{_escape_like(req.question)}%"),
            Entity.description.ilike(f"%{_escape_like(req.question)}%"),
        ))
        .order_by(Entity.mention_count.desc())
        .limit(req.max_sources)
    )).scalars().all()

    # Build context from entities
    context_parts = []
    for e in entities:
        context_parts.append(f"[{e.type}] {e.name}: {e.description or 'No description'} (mentioned {e.mention_count} times)")

    context = "\n".join(context_parts) if context_parts else "No relevant context found in organizational memory."

    # Call Claude
    from gneva.services import get_anthropic_client
    client = get_anthropic_client()

    def _call():
        return client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system="You are Gneva, an AI team member with deep knowledge of the organization's meetings, decisions, and projects. Answer questions based on the provided context from organizational memory. If the context doesn't contain enough information, say so honestly. Always cite which meetings or entities informed your answer.",
            messages=[
                {
                    "role": "user",
                    "content": f"Context from organizational memory:\n{context}\n\nQuestion: {req.question}",
                }
            ],
        )

    response = await asyncio.to_thread(_call)

    return {
        "answer": response.content[0].text,
        "sources": [
            {
                "entity_id": str(e.id),
                "type": e.type,
                "name": e.name,
                "relevance": "keyword_match",
            }
            for e in entities
        ],
    }
