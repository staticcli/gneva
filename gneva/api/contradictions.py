"""Contradiction detection alert endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.db import get_db
from gneva.models.user import User
from gneva.models.entity import Contradiction, Entity
from gneva.auth import get_current_user

router = APIRouter(prefix="/api/contradictions", tags=["contradictions"])


@router.get("/active")
async def active_contradictions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contras = (await db.execute(
        select(Contradiction)
        .where(
            Contradiction.org_id == user.org_id,
            Contradiction.status == "open",
        )
        .order_by(Contradiction.detected_at.desc())
    )).scalars().all()

    results = []
    for c in contras:
        entity_a = (await db.execute(
            select(Entity).where(Entity.id == c.entity_id_a)
        )).scalar_one_or_none()
        entity_b = (await db.execute(
            select(Entity).where(Entity.id == c.entity_id_b)
        )).scalar_one_or_none()

        results.append({
            "id": str(c.id),
            "description": c.description,
            "severity": c.severity,
            "status": c.status,
            "detected_at": c.detected_at.isoformat(),
            "entity_a": {
                "id": str(entity_a.id),
                "name": entity_a.name,
                "type": entity_a.type,
            } if entity_a else None,
            "entity_b": {
                "id": str(entity_b.id),
                "name": entity_b.name,
                "type": entity_b.type,
            } if entity_b else None,
        })

    return {"total": len(results), "contradictions": results}


class ResolveRequest(BaseModel):
    resolution_note: str


@router.post("/{contradiction_id}/resolve")
async def resolve_contradiction(
    contradiction_id: uuid.UUID,
    body: ResolveRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contra = (await db.execute(
        select(Contradiction).where(
            Contradiction.id == contradiction_id,
            Contradiction.org_id == user.org_id,
        )
    )).scalar_one_or_none()
    if not contra:
        raise HTTPException(status_code=404, detail="Contradiction not found")

    contra.status = "resolved"
    contra.resolved_at = datetime.utcnow()

    # Store resolution note on one of the related entities' metadata
    entity_a = (await db.execute(
        select(Entity).where(Entity.id == contra.entity_id_a)
    )).scalar_one_or_none()
    if entity_a:
        meta = entity_a.metadata_json or {}
        resolutions = meta.get("contradiction_resolutions", [])
        resolutions.append({
            "contradiction_id": str(contradiction_id),
            "resolution_note": body.resolution_note,
            "resolved_by": str(user.id),
            "resolved_at": datetime.utcnow().isoformat(),
        })
        meta["contradiction_resolutions"] = resolutions
        entity_a.metadata_json = meta

    return {"status": "resolved", "id": str(contradiction_id)}
