"""Agent profile and meeting assignment models."""

import uuid
from datetime import datetime

from sqlalchemy import String, ForeignKey, Float, Integer, Boolean, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gneva.db import Base
from gneva.models.compat import CompatUUID, new_uuid


class AgentProfile(Base):
    """Defines a Gneva agent persona with its capabilities and configuration."""

    __tablename__ = "agent_profiles"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID | None] = mapped_column(CompatUUID(), ForeignKey("organizations.id"), nullable=True)

    # Identity
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # "tia", "cipher", "vex"
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)  # "Tia", "Cipher"
    role: Mapped[str] = mapped_column(String(200), nullable=False)  # "Meeting Intelligence Lead"
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="core")  # "core" or "specialist"
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Voice / Personality
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    voice_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # voice_config: {pace_wpm, fillers[], signatures[], never_say[], tts_voice_id}
    avatar_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Capabilities
    tools: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # List of tool names this agent can use: ["create_action_item", "web_search", ...]
    model_default: Mapped[str] = mapped_column(String(100), nullable=False, default="claude-sonnet-4-6")
    model_complex: Mapped[str] = mapped_column(String(100), nullable=False, default="claude-sonnet-4-6")
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=300)

    # Behavior tuning
    proactivity_level: Mapped[int] = mapped_column(Integer, nullable=False, default=3)  # 1-5
    formality_level: Mapped[int] = mapped_column(Integer, nullable=False, default=3)  # 1-5
    detail_level: Mapped[int] = mapped_column(Integer, nullable=False, default=3)  # 1-5
    max_talk_time_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.15)  # 15%
    speak_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)  # 0-1

    # Status
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # builtin agents have org_id=None and can't be deleted

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    meeting_assignments: Mapped[list["MeetingAgentAssignment"]] = relationship(back_populates="agent")
    performance_scores: Mapped[list["AgentPerformance"]] = relationship(back_populates="agent")


class MeetingAgentAssignment(Base):
    """Assigns agents to meetings — which agents participate in which meetings."""

    __tablename__ = "meeting_agent_assignments"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    meeting_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("meetings.id"), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("agent_profiles.id"), nullable=False)

    # Assignment config
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    # "active" = can speak, "silent" = observe only, "on_demand" = summoned when needed
    joined_at: Mapped[datetime | None] = mapped_column(nullable=True)
    left_at: Mapped[datetime | None] = mapped_column(nullable=True)
    summoned_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # agent name that summoned this one (e.g., "tia")

    # Runtime stats
    times_spoken: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tools_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_consumed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    agent: Mapped["AgentProfile"] = relationship(back_populates="meeting_assignments")


class AgentPerformance(Base):
    """Tracks agent performance metrics per meeting for calibration."""

    __tablename__ = "agent_performance"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(CompatUUID(), ForeignKey("agent_profiles.id"), nullable=True)
    meeting_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("meetings.id"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("organizations.id"), nullable=False)

    # 5-dimension scores (0-100)
    accuracy_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    helpfulness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    timing_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    tone_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    restraint_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Composite
    composite_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Agent-specific metrics stored as JSON
    domain_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # e.g. for Tia: {"action_items_captured": 5, "decisions_detected": 3, "routing_accuracy": 0.9}

    # Feedback
    participant_rating: Mapped[float | None] = mapped_column(Float, nullable=True)  # 1-5
    participant_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Relationships
    agent: Mapped["AgentProfile"] = relationship(back_populates="performance_scores")


class AgentMessage(Base):
    """Inter-agent communication log — messages agents send to each other."""

    __tablename__ = "agent_messages"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    meeting_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("meetings.id"), nullable=False)

    from_agent: Mapped[str] = mapped_column(String(50), nullable=False)  # agent name
    to_agent: Mapped[str] = mapped_column(String(50), nullable=False)  # agent name or "all"
    message_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # "query", "inform", "deliberate", "delegate", "correct"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    urgency: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="internal")

    # Response (if query)
    response_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class AgentMemory(Base):
    """Shared agent memory that persists across meetings (Memory Mesh)."""
    __tablename__ = "agent_memories"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("organizations.id"), nullable=False, index=True)
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)  # fact, preference, decision, insight, warning
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_agent: Mapped[str] = mapped_column(String(100), nullable=False)
    source_meeting_id: Mapped[uuid.UUID | None] = mapped_column(CompatUUID(), ForeignKey("meetings.id"), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.5)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(nullable=True)


class AgentTrainingData(Base):
    """Organization-specific training data for agent customization."""

    __tablename__ = "agent_training_data"

    id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), primary_key=True, default=new_uuid)
    org_id: Mapped[uuid.UUID] = mapped_column(CompatUUID(), ForeignKey("organizations.id"), nullable=False, index=True)
    data_type: Mapped[str] = mapped_column(String(50), nullable=False)  # vocabulary, style, score
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
