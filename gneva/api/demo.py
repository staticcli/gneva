"""Demo endpoints — create sample meetings to showcase the full pipeline without Recall.ai."""

import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.db import get_db
from gneva.models.user import User
from gneva.models.meeting import Meeting, Transcript, TranscriptSegment, MeetingSummary
from gneva.models.entity import Entity, EntityRelationship, EntityMention, Decision, ActionItem
from gneva.auth import get_current_user
from gneva.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/demo", tags=["demo"])
settings = get_settings()

SAMPLE_TRANSCRIPT = """
Sarah Chen: Alright everyone, let's get started. Thanks for joining the Q2 planning session. We have a lot to cover today.

Marcus Rodriguez: Thanks Sarah. Before we dive in, quick update on the authentication project — we're about 80% done with the OAuth2 implementation. Should be ready for testing by end of next week.

Sarah Chen: Great. That's ahead of schedule. James, how's the mobile app coming along?

James Park: We hit a snag with the push notification system on Android. The Firebase integration is causing some battery drain issues. I'm working with the team to optimize it, but it might push our timeline back by about a week.

Sarah Chen: Okay, that's manageable. Let's flag that and revisit next standup. Now, the big topic — Q2 roadmap prioritization. I've been looking at the customer feedback data, and there are three features that keep coming up.

Priya Patel: Let me guess — the analytics dashboard, the API rate limiting, and the team collaboration features?

Sarah Chen: Exactly. So here's my proposal: we prioritize the analytics dashboard first because it's the number one requested feature and it directly impacts our enterprise sales pipeline. Chen from the sales team told me we lost two deals last month specifically because we didn't have proper analytics.

Marcus Rodriguez: I agree with analytics first. But I want to make sure we don't neglect the API rate limiting. We had three incidents last month where large customers overwhelmed our API. That's a reliability issue.

James Park: Can we do both in parallel? My team could take the rate limiting while the backend team handles analytics.

Sarah Chen: I like that approach. Let's do it. Marcus, can you own the analytics dashboard? Target is end of April for an MVP.

Marcus Rodriguez: Done. I'll draft a technical spec by Friday.

Priya Patel: What about the collaboration features? We promised the Acme Corp team they'd have shared workspaces by Q2.

Sarah Chen: Good point. Let's push that to the second half of Q2 — May timeframe. Priya, can you start scoping that out? I want a full PRD by end of March.

Priya Patel: On it. I'll schedule interviews with the Acme team next week to make sure we nail the requirements.

Sarah Chen: Perfect. One more thing — we need to decide on the database migration. We've been talking about moving from MySQL to PostgreSQL for months. Is Q2 the right time?

Marcus Rodriguez: I'd say yes, but not until after the analytics dashboard ships. We don't want to do a database migration and a major feature launch at the same time. I'd target late May or early June.

James Park: Agreed. The migration will also help with the analytics workload — PostgreSQL handles complex queries much better.

Sarah Chen: Alright, decision made. Database migration happens in late Q2, after analytics ships. Marcus, add that to the roadmap.

Sarah Chen: Last item — hiring. We have budget for two more engineers. I want one senior backend and one mid-level frontend. Priya, can you work with HR to get those job postings up this week?

Priya Patel: Already started the job descriptions. I'll have them posted by Wednesday.

Sarah Chen: Amazing. Okay, let me summarize the action items. Marcus — analytics dashboard tech spec by Friday, own the MVP by end of April. James — resolve the push notification issue, own API rate limiting in parallel. Priya — PRD for collaboration features by end of March, job postings by Wednesday. And the database migration is greenlit for late Q2. Anything else?

Marcus Rodriguez: One thing — can we schedule a design review for the analytics dashboard next Tuesday? I want to align with the design team early.

Sarah Chen: Great idea. I'll send the invite. Okay, we're done. Thanks everyone!
"""

SAMPLE_SEGMENTS = [
    {"speaker": "Sarah Chen", "start_ms": 0, "end_ms": 12000, "text": "Alright everyone, let's get started. Thanks for joining the Q2 planning session. We have a lot to cover today."},
    {"speaker": "Marcus Rodriguez", "start_ms": 13000, "end_ms": 28000, "text": "Thanks Sarah. Before we dive in, quick update on the authentication project — we're about 80% done with the OAuth2 implementation. Should be ready for testing by end of next week."},
    {"speaker": "Sarah Chen", "start_ms": 29000, "end_ms": 35000, "text": "Great. That's ahead of schedule. James, how's the mobile app coming along?"},
    {"speaker": "James Park", "start_ms": 36000, "end_ms": 55000, "text": "We hit a snag with the push notification system on Android. The Firebase integration is causing some battery drain issues. I'm working with the team to optimize it, but it might push our timeline back by about a week."},
    {"speaker": "Sarah Chen", "start_ms": 56000, "end_ms": 72000, "text": "Okay, that's manageable. Let's flag that and revisit next standup. Now, the big topic — Q2 roadmap prioritization. I've been looking at the customer feedback data, and there are three features that keep coming up."},
    {"speaker": "Priya Patel", "start_ms": 73000, "end_ms": 80000, "text": "Let me guess — the analytics dashboard, the API rate limiting, and the team collaboration features?"},
    {"speaker": "Sarah Chen", "start_ms": 81000, "end_ms": 105000, "text": "Exactly. So here's my proposal: we prioritize the analytics dashboard first because it's the number one requested feature and it directly impacts our enterprise sales pipeline. Chen from the sales team told me we lost two deals last month specifically because we didn't have proper analytics."},
    {"speaker": "Marcus Rodriguez", "start_ms": 106000, "end_ms": 120000, "text": "I agree with analytics first. But I want to make sure we don't neglect the API rate limiting. We had three incidents last month where large customers overwhelmed our API. That's a reliability issue."},
    {"speaker": "James Park", "start_ms": 121000, "end_ms": 130000, "text": "Can we do both in parallel? My team could take the rate limiting while the backend team handles analytics."},
    {"speaker": "Sarah Chen", "start_ms": 131000, "end_ms": 142000, "text": "I like that approach. Let's do it. Marcus, can you own the analytics dashboard? Target is end of April for an MVP."},
    {"speaker": "Marcus Rodriguez", "start_ms": 143000, "end_ms": 148000, "text": "Done. I'll draft a technical spec by Friday."},
    {"speaker": "Priya Patel", "start_ms": 149000, "end_ms": 158000, "text": "What about the collaboration features? We promised the Acme Corp team they'd have shared workspaces by Q2."},
    {"speaker": "Sarah Chen", "start_ms": 159000, "end_ms": 172000, "text": "Good point. Let's push that to the second half of Q2 — May timeframe. Priya, can you start scoping that out? I want a full PRD by end of March."},
    {"speaker": "Priya Patel", "start_ms": 173000, "end_ms": 182000, "text": "On it. I'll schedule interviews with the Acme team next week to make sure we nail the requirements."},
    {"speaker": "Sarah Chen", "start_ms": 183000, "end_ms": 198000, "text": "Perfect. One more thing — we need to decide on the database migration. We've been talking about moving from MySQL to PostgreSQL for months. Is Q2 the right time?"},
    {"speaker": "Marcus Rodriguez", "start_ms": 199000, "end_ms": 215000, "text": "I'd say yes, but not until after the analytics dashboard ships. We don't want to do a database migration and a major feature launch at the same time. I'd target late May or early June."},
    {"speaker": "James Park", "start_ms": 216000, "end_ms": 225000, "text": "Agreed. The migration will also help with the analytics workload — PostgreSQL handles complex queries much better."},
    {"speaker": "Sarah Chen", "start_ms": 226000, "end_ms": 238000, "text": "Alright, decision made. Database migration happens in late Q2, after analytics ships. Marcus, add that to the roadmap."},
    {"speaker": "Sarah Chen", "start_ms": 239000, "end_ms": 255000, "text": "Last item — hiring. We have budget for two more engineers. I want one senior backend and one mid-level frontend. Priya, can you work with HR to get those job postings up this week?"},
    {"speaker": "Priya Patel", "start_ms": 256000, "end_ms": 262000, "text": "Already started the job descriptions. I'll have them posted by Wednesday."},
    {"speaker": "Sarah Chen", "start_ms": 263000, "end_ms": 295000, "text": "Amazing. Okay, let me summarize the action items. Marcus — analytics dashboard tech spec by Friday, own the MVP by end of April. James — resolve the push notification issue, own API rate limiting in parallel. Priya — PRD for collaboration features by end of March, job postings by Wednesday. And the database migration is greenlit for late Q2. Anything else?"},
    {"speaker": "Marcus Rodriguez", "start_ms": 296000, "end_ms": 308000, "text": "One thing — can we schedule a design review for the analytics dashboard next Tuesday? I want to align with the design team early."},
    {"speaker": "Sarah Chen", "start_ms": 309000, "end_ms": 318000, "text": "Great idea. I'll send the invite. Okay, we're done. Thanks everyone!"},
]


class DemoMeetingRequest(BaseModel):
    title: str = "Q2 Planning Session"
    run_ai: bool = True  # run Claude extraction + summary


@router.post("/meeting")
async def create_demo_meeting(
    req: DemoMeetingRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a demo meeting with sample transcript and run the AI pipeline."""
    now = datetime.utcnow()

    # 1. Create meeting
    meeting = Meeting(
        org_id=user.org_id,
        platform="zoom",
        title=req.title,
        started_at=now - timedelta(minutes=5, seconds=18),
        ended_at=now,
        duration_sec=318,
        participant_count=4,
        status="complete",
    )
    db.add(meeting)
    await db.flush()

    # 2. Create transcript
    transcript = Transcript(
        meeting_id=meeting.id,
        version=1,
        full_text=SAMPLE_TRANSCRIPT.strip(),
        word_count=len(SAMPLE_TRANSCRIPT.split()),
        language="en",
    )
    db.add(transcript)
    await db.flush()

    # 3. Create segments
    for seg in SAMPLE_SEGMENTS:
        segment = TranscriptSegment(
            transcript_id=transcript.id,
            speaker_label=seg["speaker"],
            start_ms=seg["start_ms"],
            end_ms=seg["end_ms"],
            text=seg["text"],
            confidence=0.95,
        )
        db.add(segment)
    await db.flush()

    result = {
        "meeting_id": str(meeting.id),
        "status": "complete",
        "segments": len(SAMPLE_SEGMENTS),
        "ai_extraction": None,
        "ai_summary": None,
    }

    # 4. Run AI pipeline if requested
    if req.run_ai and settings.anthropic_api_key:
        try:
            # Entity extraction
            from gneva.pipeline.extractor import extract_entities
            extraction = extract_entities(SAMPLE_TRANSCRIPT.strip())

            # Helper: find existing entity or create new one
            from gneva.pipeline.resolver import canonicalize
            from sqlalchemy import select

            async def get_or_create_entity(org_id, etype, name, description=None):
                canonical = canonicalize(name)
                result = await db.execute(
                    select(Entity).where(
                        Entity.org_id == org_id,
                        Entity.type == etype,
                        Entity.canonical == canonical,
                    )
                )
                existing = result.scalar_one_or_none()
                if existing:
                    return existing
                entity = Entity(
                    org_id=org_id, type=etype, name=name,
                    canonical=canonical, description=description,
                )
                db.add(entity)
                await db.flush()
                return entity

            entity_map = {}

            for person in extraction.people:
                name = person.get("name", "Unknown")
                entity = await get_or_create_entity(user.org_id, "person", name, person.get("role"))
                entity_map[name] = entity
                db.add(EntityMention(entity_id=entity.id, meeting_id=meeting.id, mention_type="referenced"))

            for project in extraction.projects:
                name = project.get("name", "Unknown")
                entity = await get_or_create_entity(user.org_id, "project", name, project.get("status"))
                entity_map[name] = entity
                db.add(EntityMention(entity_id=entity.id, meeting_id=meeting.id, mention_type="referenced"))

            for topic in extraction.topics:
                name = topic.get("name", "Unknown")
                entity = await get_or_create_entity(user.org_id, "topic", name)
                db.add(EntityMention(entity_id=entity.id, meeting_id=meeting.id, mention_type="referenced"))

            for dec in extraction.decisions:
                statement = dec.get("statement", "")
                entity = await get_or_create_entity(user.org_id, "decision", statement[:100], dec.get("rationale"))
                db.add(Decision(
                    entity_id=entity.id, org_id=user.org_id, meeting_id=meeting.id,
                    statement=statement, rationale=dec.get("rationale"),
                    confidence=dec.get("confidence", 0.9),
                ))
                db.add(EntityMention(entity_id=entity.id, meeting_id=meeting.id, mention_type="introduced"))

            for ai in extraction.action_items:
                desc = ai.get("description", "")
                entity = await get_or_create_entity(user.org_id, "action_item", desc[:100])
                db.add(ActionItem(
                    entity_id=entity.id, org_id=user.org_id, meeting_id=meeting.id,
                    description=desc, priority=ai.get("priority", "medium"),
                ))
                db.add(EntityMention(entity_id=entity.id, meeting_id=meeting.id, mention_type="introduced"))

            await db.flush()

            result["ai_extraction"] = {
                "people": len(extraction.people),
                "projects": len(extraction.projects),
                "decisions": len(extraction.decisions),
                "action_items": len(extraction.action_items),
                "topics": len(extraction.topics),
            }

            # Summary generation
            from gneva.pipeline.summarizer import generate_summary
            entities_ctx = "\n".join(
                f"- {e.type}: {e.name}" for e in entity_map.values()
            )
            summary_result = generate_summary(SAMPLE_TRANSCRIPT.strip(), entities_ctx)

            summary = MeetingSummary(
                meeting_id=meeting.id,
                tldr=summary_result.tldr,
                key_decisions=summary_result.key_decisions,
                action_items_json=json.dumps(summary_result.action_items),
                topics_covered=summary_result.topics_covered,
                sentiment=summary_result.sentiment,
                follow_up_needed=summary_result.follow_up_needed,
            )
            db.add(summary)

            result["ai_summary"] = {
                "tldr": summary_result.tldr,
                "sentiment": summary_result.sentiment,
                "decisions": len(summary_result.key_decisions),
                "topics": len(summary_result.topics_covered),
            }

            logger.info(f"Demo meeting {meeting.id} created with AI extraction")

        except Exception as e:
            logger.error(f"AI pipeline error: {e}", exc_info=True)
            result["ai_error"] = str(e)

    return result
