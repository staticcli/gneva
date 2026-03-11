"""Meeting pattern detection service — analyzes meetings for recurring patterns."""

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from gneva.models.calendar import MeetingPattern
from gneva.models.entity import (
    ActionItem, Decision, Entity, EntityMention, Contradiction,
)
from gneva.models.meeting import Meeting, MeetingSummary
from gneva.models.calendar import SpeakerAnalytics
from gneva.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def detect_patterns(db: AsyncSession, org_id: str) -> list[MeetingPattern]:
    """Analyze recent meetings for patterns. Returns newly detected patterns."""
    # Load recent completed meetings (last 30 days)
    cutoff = datetime.utcnow() - timedelta(days=30)
    result = await db.execute(
        select(Meeting).where(
            and_(
                Meeting.org_id == org_id,
                Meeting.status == "complete",
                Meeting.created_at >= cutoff,
            )
        ).order_by(Meeting.created_at.desc())
    )
    meetings = list(result.scalars().all())

    if len(meetings) < 2:
        logger.info(f"Org {org_id}: fewer than 2 meetings, skipping pattern detection")
        return []

    patterns = []
    patterns.extend(await _detect_recurring_topics(db, org_id, meetings))
    patterns.extend(await _detect_sentiment_trends(db, org_id, meetings))
    patterns.extend(await _detect_decision_reversals(db, org_id))
    patterns.extend(await _detect_participation_gaps(db, org_id, meetings))
    patterns.extend(await _detect_repeated_blockers(db, org_id, meetings))

    await db.flush()
    logger.info(f"Org {org_id}: detected {len(patterns)} new patterns")
    return patterns


async def _detect_recurring_topics(
    db: AsyncSession, org_id: str, meetings: list[Meeting]
) -> list[MeetingPattern]:
    """Find topics that appear in 3+ meetings — may indicate unresolved issues."""
    meeting_ids = [m.id for m in meetings]

    result = await db.execute(
        select(Entity.name, Entity.id, func.count(EntityMention.id).label("cnt"))
        .join(EntityMention, EntityMention.entity_id == Entity.id)
        .where(
            and_(
                Entity.org_id == org_id,
                Entity.type == "topic",
                EntityMention.meeting_id.in_(meeting_ids),
            )
        )
        .group_by(Entity.id, Entity.name)
        .having(func.count(EntityMention.id) >= 3)
    )
    recurring = result.all()

    patterns = []
    for topic_name, topic_id, count in recurring:
        # Check if we already have this pattern
        existing = await db.execute(
            select(MeetingPattern).where(
                and_(
                    MeetingPattern.org_id == org_id,
                    MeetingPattern.pattern_type == "recurring_topic",
                    MeetingPattern.title == f"Recurring topic: {topic_name}",
                    MeetingPattern.status == "active",
                )
            )
        )
        if existing.scalar_one_or_none():
            continue

        # Get the meeting IDs where this topic appeared
        mentions_result = await db.execute(
            select(EntityMention.meeting_id).where(
                and_(
                    EntityMention.entity_id == topic_id,
                    EntityMention.meeting_id.in_(meeting_ids),
                )
            ).distinct()
        )
        mention_meeting_ids = [str(r[0]) for r in mentions_result.all()]

        pattern = MeetingPattern(
            org_id=org_id,
            pattern_type="recurring_topic",
            title=f"Recurring topic: {topic_name}",
            description=f"'{topic_name}' has been discussed in {count} meetings over the last 30 days. This may indicate an unresolved issue that needs dedicated attention.",
            confidence=min(0.5 + (count - 3) * 0.1, 0.95),
            evidence_json={"meeting_ids": mention_meeting_ids, "mention_count": count},
            severity="info" if count < 5 else "warning",
        )
        db.add(pattern)
        patterns.append(pattern)

    return patterns


async def _detect_sentiment_trends(
    db: AsyncSession, org_id: str, meetings: list[Meeting]
) -> list[MeetingPattern]:
    """Detect sentiment shifts across meetings (e.g., consistently negative)."""
    meeting_ids = [m.id for m in meetings]

    result = await db.execute(
        select(MeetingSummary.meeting_id, MeetingSummary.sentiment)
        .where(MeetingSummary.meeting_id.in_(meeting_ids))
        .order_by(MeetingSummary.created_at.desc())
    )
    summaries = result.all()

    if len(summaries) < 3:
        return []

    # Count sentiment distribution
    sentiment_counts = Counter()
    recent_sentiments = []
    for meeting_id, sentiment in summaries:
        if sentiment:
            sentiment_counts[sentiment.lower()] += 1
            recent_sentiments.append({"meeting_id": str(meeting_id), "sentiment": sentiment})

    patterns = []

    # Check for consistently negative sentiment
    negative_count = sentiment_counts.get("negative", 0) + sentiment_counts.get("frustrated", 0)
    total = sum(sentiment_counts.values())
    if total >= 3 and negative_count / total >= 0.6:
        existing = await db.execute(
            select(MeetingPattern).where(
                and_(
                    MeetingPattern.org_id == org_id,
                    MeetingPattern.pattern_type == "sentiment_trend",
                    MeetingPattern.status == "active",
                )
            )
        )
        if not existing.scalar_one_or_none():
            pattern = MeetingPattern(
                org_id=org_id,
                pattern_type="sentiment_trend",
                title="Negative sentiment trend detected",
                description=f"{negative_count} out of {total} recent meetings had negative sentiment. Team morale may need attention.",
                confidence=min(0.5 + (negative_count / total) * 0.4, 0.95),
                evidence_json={"sentiments": recent_sentiments[:10], "negative_ratio": negative_count / total},
                severity="warning" if negative_count / total < 0.8 else "critical",
            )
            db.add(pattern)
            patterns.append(pattern)

    return patterns


async def _detect_decision_reversals(
    db: AsyncSession, org_id: str
) -> list[MeetingPattern]:
    """Detect decisions that contradict or supersede previous ones."""
    result = await db.execute(
        select(Decision).where(
            and_(
                Decision.org_id == org_id,
                Decision.superseded_by.isnot(None),
            )
        ).order_by(Decision.created_at.desc()).limit(20)
    )
    reversed_decisions = result.scalars().all()

    if len(reversed_decisions) < 2:
        return []

    # Check if pattern already exists
    existing = await db.execute(
        select(MeetingPattern).where(
            and_(
                MeetingPattern.org_id == org_id,
                MeetingPattern.pattern_type == "decision_reversal",
                MeetingPattern.status == "active",
            )
        )
    )
    if existing.scalar_one_or_none():
        return []

    evidence = []
    for d in reversed_decisions[:5]:
        evidence.append({
            "decision_id": str(d.id),
            "statement": d.statement[:200],
            "meeting_id": str(d.meeting_id),
            "superseded_by": str(d.superseded_by),
        })

    pattern = MeetingPattern(
        org_id=org_id,
        pattern_type="decision_reversal",
        title=f"{len(reversed_decisions)} decisions reversed recently",
        description=f"{len(reversed_decisions)} decisions have been superseded in recent meetings. Frequent reversals may indicate unclear decision-making processes or insufficient information at decision time.",
        confidence=min(0.5 + len(reversed_decisions) * 0.1, 0.95),
        evidence_json={"reversed_decisions": evidence, "count": len(reversed_decisions)},
        severity="warning",
    )
    db.add(pattern)
    return [pattern]


async def _detect_participation_gaps(
    db: AsyncSession, org_id: str, meetings: list[Meeting]
) -> list[MeetingPattern]:
    """Detect team members who appear in earlier meetings but not recent ones."""
    if len(meetings) < 4:
        return []

    meeting_ids = [m.id for m in meetings]
    midpoint = len(meetings) // 2
    recent_ids = [m.id for m in meetings[:midpoint]]
    older_ids = [m.id for m in meetings[midpoint:]]

    # Get speakers from older meetings
    older_result = await db.execute(
        select(SpeakerAnalytics.speaker_label, SpeakerAnalytics.user_id)
        .where(SpeakerAnalytics.meeting_id.in_(older_ids))
        .distinct()
    )
    older_speakers = {(r[0], str(r[1]) if r[1] else None) for r in older_result.all()}

    # Get speakers from recent meetings
    recent_result = await db.execute(
        select(SpeakerAnalytics.speaker_label, SpeakerAnalytics.user_id)
        .where(SpeakerAnalytics.meeting_id.in_(recent_ids))
        .distinct()
    )
    recent_speakers = {(r[0], str(r[1]) if r[1] else None) for r in recent_result.all()}

    # Find speakers who were active before but not recently
    missing = older_speakers - recent_speakers
    missing_labels = [label for label, _ in missing if label]

    if len(missing_labels) < 1:
        return []

    existing = await db.execute(
        select(MeetingPattern).where(
            and_(
                MeetingPattern.org_id == org_id,
                MeetingPattern.pattern_type == "participation_gap",
                MeetingPattern.status == "active",
            )
        )
    )
    if existing.scalar_one_or_none():
        return []

    pattern = MeetingPattern(
        org_id=org_id,
        pattern_type="participation_gap",
        title=f"{len(missing_labels)} participant(s) no longer attending",
        description=f"The following participants appeared in older meetings but not in recent ones: {', '.join(missing_labels[:5])}. This may indicate disengagement or role changes.",
        confidence=0.6,
        evidence_json={"missing_speakers": missing_labels[:10]},
        severity="info",
    )
    db.add(pattern)
    return [pattern]


async def _detect_repeated_blockers(
    db: AsyncSession, org_id: str, meetings: list[Meeting]
) -> list[MeetingPattern]:
    """Detect the same issues/blockers raised repeatedly across meetings."""
    # Use action items that stay open across multiple meetings as a proxy for repeated blockers
    result = await db.execute(
        select(ActionItem).where(
            and_(
                ActionItem.org_id == org_id,
                ActionItem.status == "open",
            )
        ).order_by(ActionItem.created_at)
    )
    open_items = result.scalars().all()

    # Find action items that are old (created > 14 days ago) and still open
    cutoff = datetime.utcnow() - timedelta(days=14)
    stale_items = [
        item for item in open_items
        if item.created_at < cutoff
    ]

    if len(stale_items) < 2:
        return []

    existing = await db.execute(
        select(MeetingPattern).where(
            and_(
                MeetingPattern.org_id == org_id,
                MeetingPattern.pattern_type == "repeated_blocker",
                MeetingPattern.status == "active",
            )
        )
    )
    if existing.scalar_one_or_none():
        return []

    evidence = []
    for item in stale_items[:10]:
        age_days = (datetime.utcnow() - item.created_at).days
        evidence.append({
            "action_item_id": str(item.id),
            "description": item.description[:200],
            "age_days": age_days,
            "meeting_id": str(item.meeting_id),
        })

    pattern = MeetingPattern(
        org_id=org_id,
        pattern_type="repeated_blocker",
        title=f"{len(stale_items)} stale action items may indicate repeated blockers",
        description=f"{len(stale_items)} action items have been open for over 2 weeks. These may represent recurring blockers that the team hasn't been able to resolve.",
        confidence=min(0.5 + len(stale_items) * 0.05, 0.9),
        evidence_json={"stale_items": evidence, "count": len(stale_items)},
        severity="warning" if len(stale_items) >= 5 else "info",
    )
    db.add(pattern)
    return [pattern]
