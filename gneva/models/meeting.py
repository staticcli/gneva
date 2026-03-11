"""Meeting, Transcript, and Summary models."""

import uuid
from datetime import datetime

from sqlalchemy import String, Integer, Float, ForeignKey, Text
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from gneva.db import Base


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    recall_bot_id: Mapped[str | None] = mapped_column(String, nullable=True)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    participant_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="scheduled")
    raw_audio_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=sa_text("now()"))

    transcripts: Mapped[list["Transcript"]] = relationship(back_populates="meeting")
    summary: Mapped["MeetingSummary | None"] = relationship(back_populates="meeting", uselist=False)


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    meeting_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meetings.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sa_text("1"))
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str] = mapped_column(String, server_default="en")
    created_at: Mapped[datetime] = mapped_column(server_default=sa_text("now()"))

    meeting: Mapped["Meeting"] = relationship(back_populates="transcripts")
    segments: Mapped[list["TranscriptSegment"]] = relationship(back_populates="transcript")


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    transcript_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("transcripts.id"), nullable=False)
    speaker_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    speaker_label: Mapped[str | None] = mapped_column(String, nullable=True)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    embedding = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=sa_text("now()"))

    transcript: Mapped["Transcript"] = relationship(back_populates="segments")


class MeetingSummary(Base):
    __tablename__ = "meeting_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    meeting_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meetings.id"), unique=True, nullable=False)
    tldr: Mapped[str] = mapped_column(Text, nullable=False)
    key_decisions: Mapped[list[str]] = mapped_column(ARRAY(String), server_default=sa_text("'{}'"))
    action_items_json: Mapped[str] = mapped_column(Text, server_default="[]")  # JSON string
    topics_covered: Mapped[list[str]] = mapped_column(ARRAY(String), server_default=sa_text("'{}'"))
    sentiment: Mapped[str | None] = mapped_column(String, nullable=True)
    follow_up_needed: Mapped[bool] = mapped_column(server_default=sa_text("false"))
    embedding = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=sa_text("now()"))

    meeting: Mapped["Meeting"] = relationship(back_populates="summary")
