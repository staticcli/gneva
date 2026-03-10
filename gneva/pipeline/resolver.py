"""Entity resolution and deduplication."""

import logging
import re

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.models.entity import Entity

logger = logging.getLogger(__name__)


def canonicalize(name: str) -> str:
    """Normalize entity name for deduplication."""
    name = name.strip().lower()
    name = re.sub(r"[^\w\s]", "", name)
    name = re.sub(r"\s+", " ", name)
    return name


async def resolve_entity(
    db: AsyncSession,
    org_id,
    entity_type: str,
    name: str,
    description: str | None = None,
    embedding: list[float] | None = None,
    similarity_threshold: float = 0.92,
) -> Entity:
    """Find existing entity or create new one.

    Resolution order:
    1. Exact canonical name match
    2. Vector similarity match (if embedding provided)
    3. Create new entity
    """
    canonical = canonicalize(name)

    # 1. Exact canonical match
    existing = (await db.execute(
        select(Entity).where(
            Entity.org_id == org_id,
            Entity.type == entity_type,
            Entity.canonical == canonical,
        )
    )).scalar_one_or_none()

    if existing:
        existing.mention_count += 1
        existing.last_seen = func.now()
        if description and not existing.description:
            existing.description = description
        return existing

    # 2. Vector similarity (if embedding available)
    if embedding:
        from pgvector.sqlalchemy import Vector
        similar = (await db.execute(
            select(Entity)
            .where(Entity.org_id == org_id, Entity.type == entity_type)
            .where(Entity.embedding.isnot(None))
            .order_by(Entity.embedding.cosine_distance(embedding))
            .limit(1)
        )).scalar_one_or_none()

        if similar:
            # Calculate cosine similarity
            distance = await db.scalar(
                select(Entity.embedding.cosine_distance(embedding))
                .where(Entity.id == similar.id)
            )
            if distance is not None and (1 - distance) >= similarity_threshold:
                similar.mention_count += 1
                similar.last_seen = func.now()
                return similar

    # 3. Create new entity
    entity = Entity(
        org_id=org_id,
        type=entity_type,
        name=name,
        canonical=canonical,
        description=description,
        embedding=embedding,
    )
    db.add(entity)
    await db.flush()
    return entity
