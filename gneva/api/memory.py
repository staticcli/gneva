"""Memory / knowledge graph search and entity endpoints."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.db import get_db
from gneva.models.user import User
from gneva.models.entity import Entity, EntityRelationship, EntityMention, Decision, ActionItem, Contradiction
from gneva.auth import get_current_user

router = APIRouter(prefix="/api/memory", tags=["memory"])


def _escape_like(s: str) -> str:
    return s.replace("%", r"\%").replace("_", r"\_")


@router.get("/search")
async def search_memory(
    q: str = Query(..., min_length=1),
    type: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hybrid keyword + semantic search across org memory."""
    # For now, keyword search. Semantic search will be added when embedding pipeline is ready.
    escaped_q = _escape_like(q)
    query = (
        select(Entity)
        .where(Entity.org_id == user.org_id)
        .where(or_(
            Entity.name.ilike(f"%{escaped_q}%"),
            Entity.description.ilike(f"%{escaped_q}%"),
        ))
    )
    if type:
        query = query.where(Entity.type == type)

    query = query.order_by(Entity.mention_count.desc()).limit(limit)
    results = (await db.execute(query)).scalars().all()

    return {
        "query": q,
        "results": [
            {
                "id": str(e.id),
                "type": e.type,
                "name": e.name,
                "description": e.description,
                "mention_count": e.mention_count,
                "first_seen": e.first_seen.isoformat(),
                "last_seen": e.last_seen.isoformat(),
            }
            for e in results
        ],
    }


@router.get("/entities")
async def list_entities(
    type: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Entity).where(Entity.org_id == user.org_id)
    if type:
        query = query.where(Entity.type == type)
    query = query.order_by(Entity.last_seen.desc()).offset(offset).limit(limit)

    results = (await db.execute(query)).scalars().all()
    return {
        "entities": [
            {
                "id": str(e.id),
                "type": e.type,
                "name": e.name,
                "description": e.description,
                "mention_count": e.mention_count,
                "first_seen": e.first_seen.isoformat(),
                "last_seen": e.last_seen.isoformat(),
            }
            for e in results
        ],
    }


@router.get("/entities/{entity_id}")
async def get_entity(
    entity_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entity = (await db.execute(
        select(Entity).where(Entity.id == entity_id, Entity.org_id == user.org_id)
    )).scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Get relationships
    rels_out = (await db.execute(
        select(EntityRelationship).where(EntityRelationship.source_id == entity_id, EntityRelationship.org_id == user.org_id)
    )).scalars().all()
    rels_in = (await db.execute(
        select(EntityRelationship).where(EntityRelationship.target_id == entity_id, EntityRelationship.org_id == user.org_id)
    )).scalars().all()

    return {
        "id": str(entity.id),
        "type": entity.type,
        "name": entity.name,
        "description": entity.description,
        "mention_count": entity.mention_count,
        "first_seen": entity.first_seen.isoformat(),
        "last_seen": entity.last_seen.isoformat(),
        "relationships_out": [
            {"target_id": str(r.target_id), "relationship": r.relationship, "confidence": r.confidence}
            for r in rels_out
        ],
        "relationships_in": [
            {"source_id": str(r.source_id), "relationship": r.relationship, "confidence": r.confidence}
            for r in rels_in
        ],
    }


@router.get("/decisions")
async def list_decisions(
    status: str = "active",
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(Decision).where(Decision.org_id == user.org_id, Decision.status == status)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    decisions = (await db.execute(
        base.order_by(Decision.created_at.desc()).offset(offset).limit(limit)
    )).scalars().all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "decisions": [
            {
                "id": str(d.id),
                "statement": d.statement,
                "rationale": d.rationale,
                "status": d.status,
                "confidence": d.confidence,
                "created_at": d.created_at.isoformat(),
            }
            for d in decisions
        ],
    }


@router.get("/contradictions")
async def list_contradictions(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(Contradiction).where(Contradiction.org_id == user.org_id, Contradiction.status == "open")

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    contradictions = (await db.execute(
        base.order_by(Contradiction.detected_at.desc()).offset(offset).limit(limit)
    )).scalars().all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "contradictions": [
            {
                "id": str(c.id),
                "description": c.description,
                "severity": c.severity,
                "detected_at": c.detected_at.isoformat(),
            }
            for c in contradictions
        ],
    }
