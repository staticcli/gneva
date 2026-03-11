"""Calendar, consent, notification, and follow-up models."""

import uuid
from datetime import datetime, date

from sqlalchemy import String, Integer, Float, ForeignKey, Text, Date, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from gneva.db import Base
from gneva.models.compat import CompatUUID, new_uuid


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("users.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    meeting_url: Mapped[str | None] = mapped_column(String, nullable=True)
    platform: Mapped[str | None] = mapped_column(String, nullable=True)
    start_time: Mapped[datetime] = mapped_column(nullable=False)
    end_time: Mapped[datetime] = mapped_column(nullable=False)
    attendees_json: Mapped[list] = mapped_column(JSON, default=list)
    auto_join: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(CompatUUID(), ForeignKey("meetings.id"), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class ConsentLog(Base):
    __tablename__ = "consent_logs"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("organizations.id"), nullable=False)
    meeting_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("meetings.id"), nullable=False)
    consent_type: Mapped[str] = mapped_column(String, nullable=False)
    method: Mapped[str] = mapped_column(String, nullable=False)
    acknowledged_by: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(CompatUUID(), ForeignKey("meetings.id"), nullable=True)
    action_item_id: Mapped[uuid.UUID | None] = mapped_column(CompatUUID(), ForeignKey("action_items.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String, nullable=False, default="in_app")
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class MeetingPattern(Base):
    __tablename__ = "meeting_patterns"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("organizations.id"), nullable=False)
    pattern_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=list)
    severity: Mapped[str] = mapped_column(String, nullable=False, default="info")
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    detected_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    dismissed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class FollowUp(Base):
    __tablename__ = "follow_ups"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("organizations.id"), nullable=False)
    action_item_id: Mapped[uuid.UUID | None] = mapped_column(CompatUUID(), ForeignKey("action_items.id"), nullable=True)
    meeting_id: Mapped[uuid.UUID | None] = mapped_column(CompatUUID(), ForeignKey("meetings.id"), nullable=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(CompatUUID(), ForeignKey("users.id"), nullable=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    reminder_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reminded_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class SpeakerAnalytics(Base):
    __tablename__ = "speaker_analytics"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("organizations.id"), nullable=False)
    meeting_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("meetings.id"), nullable=False)
    speaker_label: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(CompatUUID(), ForeignKey("users.id"), nullable=True)
    talk_time_sec: Mapped[float] = mapped_column(Float, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    interruption_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sentiment_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    topics_json: Mapped[dict] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
