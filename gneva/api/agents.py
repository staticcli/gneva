"""Agent management API — CRUD for agent profiles, meeting assignments, performance."""

import uuid
import logging
from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.db import get_db
from gneva.models.user import User
from gneva.models.meeting import Meeting
from gneva.models.agent import AgentProfile, MeetingAgentAssignment, AgentPerformance, AgentMessage
from gneva.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents", tags=["agents"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class AgentProfileResponse(BaseModel):
    id: str
    name: str
    display_name: str
    role: str
    category: str
    description: str
    tools: list[str] | None
    model_default: str
    voice_config: dict | None
    avatar_path: str | None
    proactivity_level: int
    formality_level: int
    detail_level: int
    max_talk_time_pct: float
    enabled: bool
    is_builtin: bool

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v):
        return str(v) if v is not None else v

    class Config:
        from_attributes = True


class AgentProfileUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    voice_config: dict | None = None
    avatar_path: str | None = None
    proactivity_level: int | None = Field(None, ge=1, le=5)
    formality_level: int | None = Field(None, ge=1, le=5)
    detail_level: int | None = Field(None, ge=1, le=5)
    max_talk_time_pct: float | None = Field(None, ge=0.0, le=1.0)
    speak_threshold: float | None = Field(None, ge=0.0, le=1.0)
    enabled: bool | None = None


class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str = Field(..., min_length=1, max_length=100)
    role: str = Field(..., min_length=1, max_length=200)
    category: str = "specialist"
    description: str = ""
    system_prompt: str = ""
    voice_config: dict | None = None
    avatar_path: str | None = None
    tools: list[str] | None = None
    model_default: str = "claude-sonnet-4-6"
    proactivity_level: int = Field(3, ge=1, le=5)
    formality_level: int = Field(3, ge=1, le=5)
    detail_level: int = Field(3, ge=1, le=5)


class MeetingAssignmentRequest(BaseModel):
    agent_id: str | None = None
    agent_name: str | None = None  # alternative to agent_id
    mode: str = "active"  # "active", "silent", "on_demand"


class MeetingAssignmentResponse(BaseModel):
    id: str
    meeting_id: str
    agent_id: str
    agent_name: str
    agent_display_name: str
    mode: str
    joined_at: datetime | None
    left_at: datetime | None
    summoned_by: str | None
    times_spoken: int
    tools_used: int
    tokens_consumed: int

    class Config:
        from_attributes = True


class AgentPerformanceResponse(BaseModel):
    agent_name: str
    meeting_count: int
    avg_composite_score: float | None
    avg_accuracy: float | None
    avg_helpfulness: float | None
    avg_timing: float | None
    avg_tone: float | None
    avg_restraint: float | None
    avg_participant_rating: float | None


# ── Agent CRUD ───────────────────────────────────────────────────────────────

@router.get("", response_model=list[AgentProfileResponse])
async def list_agents(
    category: str | None = Query(None, description="Filter: 'core' or 'specialist'"),
    enabled_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all available agents (builtin + org-custom)."""
    q = select(AgentProfile).where(
        (AgentProfile.org_id == user.org_id) | (AgentProfile.org_id.is_(None))
    )
    if category:
        q = q.where(AgentProfile.category == category)
    if enabled_only:
        q = q.where(AgentProfile.enabled == True)
    q = q.order_by(AgentProfile.category, AgentProfile.name)
    result = await db.execute(q)
    agents = result.scalars().all()
    return [AgentProfileResponse.model_validate(a) for a in agents]


@router.get("/{agent_name}", response_model=AgentProfileResponse)
async def get_agent(
    agent_name: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a specific agent by name."""
    agent = await _resolve_agent(db, agent_name, user.org_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    return AgentProfileResponse.model_validate(agent)


@router.post("", response_model=AgentProfileResponse, status_code=201)
async def create_agent(
    req: AgentCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a custom agent for this organization."""
    # Check name not taken
    existing = await _resolve_agent(db, req.name, user.org_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Agent '{req.name}' already exists")

    agent = AgentProfile(
        org_id=user.org_id,
        name=req.name,
        display_name=req.display_name,
        role=req.role,
        category=req.category,
        description=req.description,
        system_prompt=req.system_prompt,
        voice_config=req.voice_config,
        avatar_path=req.avatar_path,
        tools=req.tools,
        model_default=req.model_default,
        proactivity_level=req.proactivity_level,
        formality_level=req.formality_level,
        detail_level=req.detail_level,
        is_builtin=False,
    )
    db.add(agent)
    await db.flush()
    return AgentProfileResponse.model_validate(agent)


@router.patch("/{agent_name}", response_model=AgentProfileResponse)
async def update_agent(
    agent_name: str,
    req: AgentProfileUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update agent configuration. Builtin agents get org-level overrides."""
    agent = await _resolve_agent(db, agent_name, user.org_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    # For builtin agents, create an org-level override copy
    if agent.is_builtin and agent.org_id is None:
        agent = await _create_org_override(db, agent, user.org_id)

    updates = req.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(agent, field, value)
    agent.updated_at = datetime.utcnow()
    await db.flush()
    return AgentProfileResponse.model_validate(agent)


@router.delete("/{agent_name}", status_code=204)
async def delete_agent(
    agent_name: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a custom agent. Cannot delete builtin agents."""
    agent = await _resolve_agent(db, agent_name, user.org_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    if agent.is_builtin and agent.org_id is None:
        raise HTTPException(status_code=403, detail="Cannot delete builtin agents")
    await db.delete(agent)


# ── Meeting Agent Assignments ────────────────────────────────────────────────

@router.post("/meetings/{meeting_id}/assign", response_model=MeetingAssignmentResponse)
async def assign_agent_to_meeting(
    meeting_id: str,
    req: MeetingAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Assign an agent to a meeting."""
    try:
        mid = uuid.UUID(meeting_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid meeting_id format")

    await _verify_meeting_ownership(db, mid, user.org_id)

    # Resolve agent
    if req.agent_name:
        agent = await _resolve_agent(db, req.agent_name, user.org_id)
    elif req.agent_id:
        result = await db.execute(select(AgentProfile).where(
            and_(AgentProfile.id == uuid.UUID(req.agent_id),
                 (AgentProfile.org_id == user.org_id) | (AgentProfile.org_id.is_(None)))
        ))
        agent = result.scalar_one_or_none()
    else:
        raise HTTPException(status_code=400, detail="Provide agent_id or agent_name")

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Check not already assigned
    existing = await db.execute(
        select(MeetingAgentAssignment).where(
            and_(MeetingAgentAssignment.meeting_id == mid, MeetingAgentAssignment.agent_id == agent.id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Agent '{agent.name}' already assigned to this meeting")

    assignment = MeetingAgentAssignment(
        meeting_id=mid,
        agent_id=agent.id,
        mode=req.mode,
        joined_at=datetime.utcnow() if req.mode == "active" else None,
    )
    db.add(assignment)
    await db.flush()

    return MeetingAssignmentResponse(
        id=str(assignment.id),
        meeting_id=str(mid),
        agent_id=str(agent.id),
        agent_name=agent.name,
        agent_display_name=agent.display_name,
        mode=assignment.mode,
        joined_at=assignment.joined_at,
        left_at=assignment.left_at,
        summoned_by=assignment.summoned_by,
        times_spoken=assignment.times_spoken,
        tools_used=assignment.tools_used,
        tokens_consumed=assignment.tokens_consumed,
    )


@router.get("/meetings/{meeting_id}/agents", response_model=list[MeetingAssignmentResponse])
async def list_meeting_agents(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all agents assigned to a meeting."""
    try:
        mid = uuid.UUID(meeting_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid meeting_id format")

    await _verify_meeting_ownership(db, mid, user.org_id)

    result = await db.execute(
        select(MeetingAgentAssignment, AgentProfile)
        .join(AgentProfile, MeetingAgentAssignment.agent_id == AgentProfile.id)
        .where(MeetingAgentAssignment.meeting_id == mid)
        .order_by(MeetingAgentAssignment.created_at)
    )
    rows = result.all()
    return [
        MeetingAssignmentResponse(
            id=str(assignment.id),
            meeting_id=str(mid),
            agent_id=str(agent.id),
            agent_name=agent.name,
            agent_display_name=agent.display_name,
            mode=assignment.mode,
            joined_at=assignment.joined_at,
            left_at=assignment.left_at,
            summoned_by=assignment.summoned_by,
            times_spoken=assignment.times_spoken,
            tools_used=assignment.tools_used,
            tokens_consumed=assignment.tokens_consumed,
        )
        for assignment, agent in rows
    ]


@router.delete("/meetings/{meeting_id}/agents/{agent_name}", status_code=204)
async def remove_agent_from_meeting(
    meeting_id: str,
    agent_name: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Remove an agent from a meeting."""
    try:
        mid = uuid.UUID(meeting_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid meeting_id format")

    await _verify_meeting_ownership(db, mid, user.org_id)

    agent = await _resolve_agent(db, agent_name, user.org_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    result = await db.execute(
        select(MeetingAgentAssignment).where(
            and_(MeetingAgentAssignment.meeting_id == mid, MeetingAgentAssignment.agent_id == agent.id)
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Agent not assigned to this meeting")

    assignment.left_at = datetime.utcnow()
    await db.flush()


# ── Performance ──────────────────────────────────────────────────────────────

@router.get("/{agent_name}/performance", response_model=AgentPerformanceResponse)
async def get_agent_performance(
    agent_name: str,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get aggregated performance metrics for an agent."""
    agent = await _resolve_agent(db, agent_name, user.org_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)

    result = await db.execute(
        select(
            func.count(AgentPerformance.id).label("meeting_count"),
            func.avg(AgentPerformance.composite_score).label("avg_composite"),
            func.avg(AgentPerformance.accuracy_score).label("avg_accuracy"),
            func.avg(AgentPerformance.helpfulness_score).label("avg_helpfulness"),
            func.avg(AgentPerformance.timing_score).label("avg_timing"),
            func.avg(AgentPerformance.tone_score).label("avg_tone"),
            func.avg(AgentPerformance.restraint_score).label("avg_restraint"),
            func.avg(AgentPerformance.participant_rating).label("avg_rating"),
        ).where(
            and_(
                AgentPerformance.agent_id == agent.id,
                AgentPerformance.org_id == user.org_id,
                AgentPerformance.created_at >= cutoff,
            )
        )
    )
    row = result.one()

    return AgentPerformanceResponse(
        agent_name=agent.name,
        meeting_count=row.meeting_count or 0,
        avg_composite_score=round(row.avg_composite, 1) if row.avg_composite else None,
        avg_accuracy=round(row.avg_accuracy, 1) if row.avg_accuracy else None,
        avg_helpfulness=round(row.avg_helpfulness, 1) if row.avg_helpfulness else None,
        avg_timing=round(row.avg_timing, 1) if row.avg_timing else None,
        avg_tone=round(row.avg_tone, 1) if row.avg_tone else None,
        avg_restraint=round(row.avg_restraint, 1) if row.avg_restraint else None,
        avg_participant_rating=round(row.avg_rating, 1) if row.avg_rating else None,
    )


# ── Inter-Agent Messages ─────────────────────────────────────────────────────

@router.get("/meetings/{meeting_id}/messages")
async def list_agent_messages(
    meeting_id: str,
    agent_name: str | None = Query(None),
    message_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List inter-agent messages for a meeting (for debugging/transparency)."""
    try:
        mid = uuid.UUID(meeting_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid meeting_id format")

    await _verify_meeting_ownership(db, mid, user.org_id)

    q = select(AgentMessage).where(AgentMessage.meeting_id == mid)
    q = q.where(AgentMessage.visibility != "internal")
    if agent_name:
        q = q.where((AgentMessage.from_agent == agent_name) | (AgentMessage.to_agent == agent_name))
    if message_type:
        q = q.where(AgentMessage.message_type == message_type)
    q = q.order_by(AgentMessage.created_at.desc()).limit(limit)
    result = await db.execute(q)
    messages = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "from_agent": m.from_agent,
            "to_agent": m.to_agent,
            "message_type": m.message_type,
            "content": m.content,
            "urgency": m.urgency,
            "visibility": m.visibility,
            "response_content": m.response_content,
            "response_confidence": m.response_confidence,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _verify_meeting_ownership(db: AsyncSession, meeting_id: uuid.UUID, org_id: uuid.UUID):
    """Verify that the meeting belongs to the user's organization. Raises 404 if not."""
    result = await db.execute(
        select(Meeting.id).where(and_(Meeting.id == meeting_id, Meeting.org_id == org_id))
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Meeting not found")


async def _resolve_agent(db: AsyncSession, name: str, org_id: uuid.UUID) -> AgentProfile | None:
    """Resolve agent by name — org-level override takes priority over builtin."""
    # Try org-specific first
    result = await db.execute(
        select(AgentProfile).where(
            and_(AgentProfile.name == name, AgentProfile.org_id == org_id)
        )
    )
    agent = result.scalar_one_or_none()
    if agent:
        return agent

    # Fall back to builtin
    result = await db.execute(
        select(AgentProfile).where(
            and_(AgentProfile.name == name, AgentProfile.org_id.is_(None), AgentProfile.is_builtin == True)
        )
    )
    return result.scalar_one_or_none()


async def _create_org_override(db: AsyncSession, builtin: AgentProfile, org_id: uuid.UUID) -> AgentProfile:
    """Create an org-level copy of a builtin agent for customization."""
    override = AgentProfile(
        org_id=org_id,
        name=builtin.name,
        display_name=builtin.display_name,
        role=builtin.role,
        category=builtin.category,
        description=builtin.description,
        system_prompt=builtin.system_prompt,
        voice_config=builtin.voice_config,
        avatar_path=builtin.avatar_path,
        tools=builtin.tools,
        model_default=builtin.model_default,
        model_complex=builtin.model_complex,
        max_tokens=builtin.max_tokens,
        proactivity_level=builtin.proactivity_level,
        formality_level=builtin.formality_level,
        detail_level=builtin.detail_level,
        max_talk_time_pct=builtin.max_talk_time_pct,
        speak_threshold=builtin.speak_threshold,
        enabled=builtin.enabled,
        is_builtin=False,
    )
    db.add(override)
    await db.flush()
    return override
