"""Async meeting processing pipeline — no Celery required."""

import asyncio
import json
import logging
import os
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def process_meeting(meeting_id: str):
    """Run the full processing pipeline for a meeting with recorded audio.

    Steps:
    1. Look up meeting, get audio_path
    2. Transcribe with faster-whisper (or skip if no audio — e.g. demo meetings)
    3. Diarize speakers (if audio available)
    4. Merge transcription + diarization into speaker-attributed segments
    5. Extract entities using LLM (Claude API or local Ollama)
    6. Generate summary using LLM
    7. Update meeting status to 'complete'
    """
    import uuid as uuid_mod
    from gneva.db import async_session_factory
    from gneva.models.meeting import Meeting, Transcript, TranscriptSegment, MeetingSummary
    from gneva.models.entity import Entity, EntityMention, Decision, ActionItem
    from gneva.config import get_settings
    from gneva.pipeline.resolver import canonicalize

    if isinstance(meeting_id, str):
        meeting_id = uuid_mod.UUID(meeting_id)

    settings = get_settings()

    async with async_session_factory() as db:
        # 1. Get meeting
        result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
        meeting = result.scalar_one_or_none()
        if not meeting:
            logger.error(f"Meeting {meeting_id} not found")
            return

        audio_path = meeting.raw_audio_path
        meeting.status = "processing"
        await db.commit()

        try:
            transcript_text = ""
            segments_data = []

            # 2-3. Transcribe and diarize (if audio exists)
            if audio_path and os.path.exists(audio_path):
                logger.info(f"Processing audio: {audio_path}")

                # Run transcription in thread pool (CPU-bound)
                loop = asyncio.get_running_loop()

                # Transcribe
                from gneva.pipeline.transcriber import transcribe
                transcription = await loop.run_in_executor(
                    None,
                    lambda: transcribe(audio_path, settings.whisper_model, settings.whisper_device)
                )
                transcript_text = transcription.full_text

                # Try diarization (may fail if pyannote not installed)
                try:
                    from gneva.pipeline.diarizer import diarize, assign_speakers
                    speaker_segments = await loop.run_in_executor(
                        None, lambda: diarize(audio_path)
                    )
                    segments_data = assign_speakers(transcription.segments, speaker_segments)
                except ImportError:
                    logger.warning("pyannote not installed — skipping diarization")
                    # Create segments without speaker labels
                    segments_data = [{
                        "speaker_label": "Speaker",
                        "start_ms": 0,
                        "end_ms": int(len(transcript_text.split()) * 300),  # rough estimate
                        "text": transcript_text,
                        "confidence": 0.9,
                    }]
                except Exception as e:
                    logger.warning(f"Diarization failed: {e}")
                    segments_data = [{
                        "speaker_label": "Speaker",
                        "start_ms": 0,
                        "end_ms": int(len(transcript_text.split()) * 300),
                        "text": transcript_text,
                        "confidence": 0.9,
                    }]
            else:
                # No audio — check if transcript already exists (demo meeting)
                tx_result = await db.execute(
                    select(Transcript).where(Transcript.meeting_id == meeting_id)
                )
                existing_transcript = tx_result.scalar_one_or_none()
                if existing_transcript:
                    transcript_text = existing_transcript.full_text
                    logger.info("Using existing transcript (no audio to process)")
                else:
                    logger.error(f"No audio and no transcript for meeting {meeting_id}")
                    meeting.status = "failed"
                    await db.commit()
                    return

            # 4. Save transcript + segments (if not already saved)
            if audio_path and transcript_text:
                # Check for existing transcript and remove it (reprocessing case)
                existing_tx = (await db.execute(
                    select(Transcript).where(Transcript.meeting_id == meeting_id)
                )).scalar_one_or_none()
                if existing_tx:
                    # Delete existing segments first, then the transcript
                    await db.execute(
                        select(TranscriptSegment).where(
                            TranscriptSegment.transcript_id == existing_tx.id
                        )
                    )
                    from sqlalchemy import delete
                    await db.execute(
                        delete(TranscriptSegment).where(
                            TranscriptSegment.transcript_id == existing_tx.id
                        )
                    )
                    await db.delete(existing_tx)
                    await db.flush()
                    logger.info(f"Deleted existing transcript for reprocessing meeting {meeting_id}")

                transcript = Transcript(
                    meeting_id=meeting_id,
                    version=1,
                    full_text=transcript_text,
                    word_count=len(transcript_text.split()),
                    language="en",
                )
                db.add(transcript)
                await db.flush()

                for seg in segments_data:
                    db.add(TranscriptSegment(
                        transcript_id=transcript.id,
                        speaker_label=seg.get("speaker_label"),
                        start_ms=seg["start_ms"],
                        end_ms=seg["end_ms"],
                        text=seg["text"],
                        confidence=seg.get("confidence", 0.9),
                    ))
                await db.flush()

            # 5. Extract entities using LLM
            if transcript_text:
                extraction = await _extract_with_llm(transcript_text, settings)

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

                for person in extraction.get("people", []):
                    name = person.get("name", "Unknown")
                    entity = await get_or_create_entity(meeting.org_id, "person", name, person.get("role"))
                    entity_map[name] = entity
                    db.add(EntityMention(entity_id=entity.id, meeting_id=meeting_id, mention_type="referenced"))

                for project in extraction.get("projects", []):
                    name = project.get("name", "Unknown")
                    entity = await get_or_create_entity(meeting.org_id, "project", name, project.get("status"))
                    entity_map[name] = entity
                    db.add(EntityMention(entity_id=entity.id, meeting_id=meeting_id, mention_type="referenced"))

                for topic in extraction.get("topics", []):
                    name = topic.get("name", "Unknown")
                    entity = await get_or_create_entity(meeting.org_id, "topic", name)
                    db.add(EntityMention(entity_id=entity.id, meeting_id=meeting_id, mention_type="referenced"))

                for dec in extraction.get("decisions", []):
                    statement = dec.get("statement", "")
                    entity = await get_or_create_entity(meeting.org_id, "decision", statement[:100], dec.get("rationale"))
                    db.add(Decision(
                        entity_id=entity.id, org_id=meeting.org_id, meeting_id=meeting_id,
                        statement=statement, rationale=dec.get("rationale"),
                        confidence=dec.get("confidence", 0.9),
                    ))
                    db.add(EntityMention(entity_id=entity.id, meeting_id=meeting_id, mention_type="introduced"))

                for ai in extraction.get("action_items", []):
                    desc = ai.get("description", "")
                    entity = await get_or_create_entity(meeting.org_id, "action_item", desc[:100])
                    db.add(ActionItem(
                        entity_id=entity.id, org_id=meeting.org_id, meeting_id=meeting_id,
                        description=desc, priority=ai.get("priority", "medium"),
                    ))
                    db.add(EntityMention(entity_id=entity.id, meeting_id=meeting_id, mention_type="introduced"))

                await db.flush()

                # 6. Generate summary
                entities_ctx = "\n".join(f"- {e.type}: {e.name}" for e in entity_map.values())
                summary_data = await _summarize_with_llm(transcript_text, entities_ctx, settings)

                summary = MeetingSummary(
                    meeting_id=meeting_id,
                    tldr=summary_data["tldr"],
                    key_decisions=summary_data.get("key_decisions", []),
                    action_items_json=json.dumps(summary_data.get("action_items", [])),
                    topics_covered=summary_data.get("topics_covered", []),
                    sentiment=summary_data.get("sentiment"),
                    follow_up_needed=summary_data.get("follow_up_needed", False),
                )
                db.add(summary)

            # 7. Mark complete
            meeting.status = "complete"
            if audio_path and segments_data:
                total_ms = max((s["end_ms"] for s in segments_data), default=0)
                meeting.duration_sec = total_ms // 1000

            await db.commit()
            logger.info(f"Pipeline complete for meeting {meeting_id}")

        except Exception as e:
            logger.error(f"Pipeline failed for meeting {meeting_id}: {e}", exc_info=True)
            meeting.status = "failed"
            await db.commit()


async def _extract_with_llm(transcript_text: str, settings) -> dict:
    """Extract entities using either Claude API or local Ollama."""
    if settings.anthropic_api_key:
        from gneva.pipeline.extractor import extract_entities
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: extract_entities(transcript_text))
        return {
            "people": result.people,
            "projects": result.projects,
            "topics": result.topics,
            "decisions": result.decisions,
            "action_items": result.action_items,
        }
    else:
        # Try local Ollama
        from gneva.pipeline.local_llm import extract_entities_local
        return await extract_entities_local(transcript_text)


async def _summarize_with_llm(transcript_text: str, entities_ctx: str, settings) -> dict:
    """Generate summary using either Claude API or local Ollama."""
    if settings.anthropic_api_key:
        from gneva.pipeline.summarizer import generate_summary
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, lambda: generate_summary(transcript_text, entities_ctx))
        return {
            "tldr": result.tldr,
            "key_decisions": result.key_decisions,
            "action_items": result.action_items,
            "topics_covered": result.topics_covered,
            "sentiment": result.sentiment,
            "follow_up_needed": result.follow_up_needed,
        }
    else:
        from gneva.pipeline.local_llm import summarize_local
        return await summarize_local(transcript_text, entities_ctx)
