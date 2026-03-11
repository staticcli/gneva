"""Speaker and meeting analytics service."""

import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.models.calendar import SpeakerAnalytics
from gneva.models.entity import ActionItem, Decision, EntityMention, Entity
from gneva.models.meeting import Meeting, Transcript, TranscriptSegment, MeetingSummary
from gneva.models.user import User

logger = logging.getLogger(__name__)


async def compute_speaker_analytics(
    db: AsyncSession, meeting_id: str | uuid.UUID
) -> list[SpeakerAnalytics]:
    """Process transcript segments to compute per-speaker analytics.

    Computes talk time, word count, question count, and interruption count
    for each speaker in the meeting.
    """
    if isinstance(meeting_id, str):
        meeting_id = uuid.UUID(meeting_id)

    # Get meeting
    meeting_result = await db.execute(
        select(Meeting).where(Meeting.id == meeting_id)
    )
    meeting = meeting_result.scalar_one_or_none()
    if not meeting:
        logger.error(f"Meeting {meeting_id} not found for analytics")
        return []

    # Get the latest transcript
    transcript_result = await db.execute(
        select(Transcript)
        .where(Transcript.meeting_id == meeting_id)
        .order_by(Transcript.version.desc())
    )
    transcript = transcript_result.scalar_one_or_none()
    if not transcript:
        logger.warning(f"No transcript for meeting {meeting_id}")
        return []

    # Get all segments ordered by start time
    segments_result = await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.transcript_id == transcript.id)
        .order_by(TranscriptSegment.start_ms)
    )
    segments = list(segments_result.scalars().all())

    if not segments:
        return []

    # Aggregate per speaker
    speaker_data = defaultdict(lambda: {
        "talk_time_ms": 0,
        "word_count": 0,
        "question_count": 0,
        "interruption_count": 0,
        "user_id": None,
        "texts": [],
    })

    prev_speaker = None
    prev_end_ms = 0

    for seg in segments:
        label = seg.speaker_label or "Unknown"
        data = speaker_data[label]

        data["talk_time_ms"] += seg.end_ms - seg.start_ms
        words = seg.text.split()
        data["word_count"] += len(words)
        data["texts"].append(seg.text)

        # Count questions (simple heuristic: ends with ?)
        if seg.text.strip().endswith("?"):
            data["question_count"] += 1

        # Detect interruptions: speaker changed while previous speaker was still talking
        # (new segment starts before previous segment ended)
        if prev_speaker and prev_speaker != label and seg.start_ms < prev_end_ms:
            data["interruption_count"] += 1

        if seg.speaker_id:
            data["user_id"] = seg.speaker_id

        prev_speaker = label
        prev_end_ms = seg.end_ms

    # Delete existing analytics for this meeting (idempotent reprocessing)
    existing = await db.execute(
        select(SpeakerAnalytics).where(SpeakerAnalytics.meeting_id == meeting_id)
    )
    for sa in existing.scalars().all():
        await db.delete(sa)
    await db.flush()

    # Create SpeakerAnalytics records
    analytics = []
    for speaker_label, data in speaker_data.items():
        sa = SpeakerAnalytics(
            org_id=meeting.org_id,
            meeting_id=meeting_id,
            speaker_label=speaker_label,
            user_id=data["user_id"],
            talk_time_sec=data["talk_time_ms"] / 1000.0,
            word_count=data["word_count"],
            interruption_count=data["interruption_count"],
            question_count=data["question_count"],
            sentiment_avg=None,  # computed separately if needed
            topics_json=[],
        )
        db.add(sa)
        analytics.append(sa)

    await db.flush()
    logger.info(f"Computed analytics for {len(analytics)} speakers in meeting {meeting_id}")
    return analytics


async def get_org_analytics(
    db: AsyncSession, org_id: str, days: int = 30
) -> dict:
    """Aggregate org-level stats over the given period.

    Returns total meetings, total hours, avg participants, top speakers, top topics.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Total meetings
    meetings_q = select(func.count()).where(
        and_(
            Meeting.org_id == org_id,
            Meeting.status == "complete",
            Meeting.created_at >= cutoff,
        )
    )
    total_meetings = (await db.execute(meetings_q)).scalar() or 0

    # Total hours
    hours_q = select(func.coalesce(func.sum(Meeting.duration_sec), 0)).where(
        and_(
            Meeting.org_id == org_id,
            Meeting.status == "complete",
            Meeting.created_at >= cutoff,
        )
    )
    total_seconds = (await db.execute(hours_q)).scalar() or 0
    total_hours = round(total_seconds / 3600, 1)

    # Avg participants
    avg_q = select(func.avg(Meeting.participant_count)).where(
        and_(
            Meeting.org_id == org_id,
            Meeting.status == "complete",
            Meeting.created_at >= cutoff,
            Meeting.participant_count.isnot(None),
        )
    )
    avg_participants = (await db.execute(avg_q)).scalar()
    avg_participants = round(float(avg_participants), 1) if avg_participants else 0.0

    # Total action items
    action_items_q = select(func.count()).where(
        and_(
            ActionItem.org_id == org_id,
            ActionItem.created_at >= cutoff,
        )
    )
    total_action_items = (await db.execute(action_items_q)).scalar() or 0

    # Open action items
    open_items_q = select(func.count()).where(
        and_(
            ActionItem.org_id == org_id,
            ActionItem.status == "open",
        )
    )
    open_action_items = (await db.execute(open_items_q)).scalar() or 0

    # Total decisions
    decisions_q = select(func.count()).where(
        and_(
            Decision.org_id == org_id,
            Decision.created_at >= cutoff,
        )
    )
    total_decisions = (await db.execute(decisions_q)).scalar() or 0

    # Top speakers by total talk time
    speakers_q = (
        select(
            SpeakerAnalytics.speaker_label,
            func.sum(SpeakerAnalytics.talk_time_sec).label("total_talk"),
            func.sum(SpeakerAnalytics.word_count).label("total_words"),
            func.count(SpeakerAnalytics.meeting_id).label("meeting_count"),
        )
        .join(Meeting, Meeting.id == SpeakerAnalytics.meeting_id)
        .where(
            and_(
                SpeakerAnalytics.org_id == org_id,
                Meeting.created_at >= cutoff,
            )
        )
        .group_by(SpeakerAnalytics.speaker_label)
        .order_by(func.sum(SpeakerAnalytics.talk_time_sec).desc())
        .limit(10)
    )
    speakers_result = await db.execute(speakers_q)
    top_speakers = [
        {
            "speaker": r[0],
            "total_talk_time_sec": round(float(r[1]), 1),
            "total_words": int(r[2]),
            "meetings_attended": int(r[3]),
        }
        for r in speakers_result.all()
    ]

    # Top topics by mention count
    topics_q = (
        select(Entity.name, func.count(EntityMention.id).label("cnt"))
        .join(EntityMention, EntityMention.entity_id == Entity.id)
        .where(
            and_(
                Entity.org_id == org_id,
                Entity.type == "topic",
                EntityMention.created_at >= cutoff,
            )
        )
        .group_by(Entity.name)
        .order_by(func.count(EntityMention.id).desc())
        .limit(10)
    )
    topics_result = await db.execute(topics_q)
    top_topics = [
        {"topic": r[0], "mention_count": int(r[1])}
        for r in topics_result.all()
    ]

    return {
        "period_days": days,
        "total_meetings": total_meetings,
        "total_hours": total_hours,
        "avg_participants": avg_participants,
        "total_action_items": total_action_items,
        "open_action_items": open_action_items,
        "total_decisions": total_decisions,
        "top_speakers": top_speakers,
        "top_topics": top_topics,
    }


async def get_speaker_profile(
    db: AsyncSession, org_id: str, user_id: str
) -> dict:
    """Get a speaker's aggregated stats across all meetings."""
    # Get user info
    user_result = await db.execute(
        select(User).where(and_(User.id == user_id, User.org_id == org_id))
    )
    user = user_result.scalar_one_or_none()

    # Aggregate speaker analytics for this user
    stats_q = (
        select(
            func.count(SpeakerAnalytics.id).label("meetings"),
            func.sum(SpeakerAnalytics.talk_time_sec).label("total_talk"),
            func.avg(SpeakerAnalytics.talk_time_sec).label("avg_talk"),
            func.sum(SpeakerAnalytics.word_count).label("total_words"),
            func.sum(SpeakerAnalytics.interruption_count).label("total_interruptions"),
            func.sum(SpeakerAnalytics.question_count).label("total_questions"),
            func.avg(SpeakerAnalytics.sentiment_avg).label("avg_sentiment"),
        )
        .where(
            and_(
                SpeakerAnalytics.org_id == org_id,
                SpeakerAnalytics.user_id == user_id,
            )
        )
    )
    result = await db.execute(stats_q)
    row = result.one_or_none()

    if not row or not row[0]:
        return {
            "user_id": str(user_id),
            "name": user.name if user else "Unknown",
            "email": user.email if user else None,
            "meetings_attended": 0,
            "total_talk_time_sec": 0,
            "avg_talk_time_sec": 0,
            "total_words": 0,
            "total_interruptions": 0,
            "total_questions": 0,
            "avg_sentiment": None,
        }

    return {
        "user_id": str(user_id),
        "name": user.name if user else "Unknown",
        "email": user.email if user else None,
        "meetings_attended": int(row[0]),
        "total_talk_time_sec": round(float(row[1] or 0), 1),
        "avg_talk_time_sec": round(float(row[2] or 0), 1),
        "total_words": int(row[3] or 0),
        "total_interruptions": int(row[4] or 0),
        "total_questions": int(row[5] or 0),
        "avg_sentiment": round(float(row[6]), 2) if row[6] else None,
    }
