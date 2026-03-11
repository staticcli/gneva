"""Knowledge graph entity models."""

import uuid
from datetime import date, datetime

from sqlalchemy import String, Integer, Float, ForeignKey, Text, Date, JSON
from sqlalchemy.orm import Mapped, mapped_column

from gneva.db import Base
from gneva.models.compat import CompatUUID, new_uuid


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("organizations.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    canonical: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding = mapped_column(JSON, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class EntityRelationship(Base):
    __tablename__ = "entity_relationships"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("organizations.id"), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("entities.id"), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("entities.id"), nullable=False)
    relationship: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(CompatUUID(), ForeignKey("meetings.id"), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    valid_until: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class EntityMention(Base):
    __tablename__ = "entity_mentions"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    entity_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("entities.id"), nullable=False)
    meeting_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("meetings.id"), nullable=False)
    segment_id: Mapped[uuid.UUID | None] = mapped_column(CompatUUID(), ForeignKey("transcript_segments.id"), nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    mention_type: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    entity_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("entities.id"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("organizations.id"), nullable=False)
    meeting_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("meetings.id"), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(CompatUUID(), ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(CompatUUID(), ForeignKey("decisions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    entity_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("entities.id"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("organizations.id"), nullable=False)
    meeting_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("meetings.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(CompatUUID(), ForeignKey("users.id"), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String, default="medium")
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class Contradiction(Base):
    __tablename__ = "contradictions"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("organizations.id"), nullable=False)
    entity_id_a: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("entities.id"), nullable=False)
    entity_id_b: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("entities.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False, default="low")
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    detected_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)


class GnevaMessage(Base):
    __tablename__ = "gneva_messages"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("organizations.id"), nullable=False)
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(CompatUUID(), ForeignKey("meetings.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    channel_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
