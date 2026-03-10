# Neva: Technical Architecture Document

**Version:** 0.1 — Initial Draft
**Date:** 2026-03-10
**Status:** Pre-build specification

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [System Architecture](#2-system-architecture)
3. [Technology Stack & Rationale](#3-technology-stack--rationale)
4. [Database Schema](#4-database-schema)
5. [API Design](#5-api-design)
6. [Processing Pipeline](#6-processing-pipeline)
7. [Memory Engine & Knowledge Graph](#7-memory-engine--knowledge-graph)
8. [Growth Stage Implementation](#8-growth-stage-implementation)
9. [Deployment Architecture](#9-deployment-architecture)
10. [Cost Analysis](#10-cost-analysis)
11. [MVP Scope & Timeline](#11-mvp-scope--timeline)
12. [Scalability Considerations](#12-scalability-considerations)

---

## 1. Product Overview

Neva is an AI team member that joins meetings, accumulates organizational memory, and progressively evolves from a silent observer into an active voice participant and autonomous project manager. Unlike meeting recording tools, Neva builds a living knowledge graph of an organization's decisions, commitments, and relationships — and uses that graph to reason, advise, and eventually act.

### Growth Stages

| Stage | Name | Capability |
|-------|------|------------|
| 1 | Silent Observer | Join meetings, transcribe, build memory silently |
| 2 | Post-Meeting Analyst | Async summaries, action items, decision logs |
| 3 | Async Team Member | Slack/Teams integration, answer org questions |
| 4 | Active Participant | Real-time voice in meetings, ask clarifying questions |
| 5 | Autonomous PM | Proactive management, represent absent members, draft PRDs |

---

## 2. System Architecture

### High-Level Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────────────┐  │
│  │  React Web   │   │  Slack App   │   │  Teams App / Webhooks  │  │
│  │  Dashboard   │   │  Integration │   │                        │  │
│  └──────┬───────┘   └──────┬───────┘   └───────────┬────────────┘  │
└─────────┼──────────────────┼───────────────────────┼───────────────┘
          │                  │                        │
          ▼                  ▼                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY (FastAPI)                       │
│                                                                     │
│  /meetings  /memory  /ask  /actions  /bot  /voice  /org  /search   │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                     Auth Middleware (JWT)                      │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐
│   MEETING BOT   │  │  TASK QUEUE     │  │   VOICE ENGINE          │
│   SERVICE       │  │  (Celery +      │  │   (Stage 4+)            │
│                 │  │   Redis)        │  │                         │
│  Recall.ai SDK  │  │                 │  │  ElevenLabs API         │
│  Bot lifecycle  │  │  - transcribe   │  │  Voice cloning          │
│  Audio capture  │  │  - extract      │  │  Turn detection         │
│  Real-time WS   │  │  - embed        │  │  Interrupt logic        │
└────────┬────────┘  │  - summarize    │  └──────────────┬──────────┘
         │           │  - notify       │                 │
         │           └────────┬────────┘                 │
         │                    │                          │
         ▼                    ▼                          │
┌─────────────────────────────────────────────────────────────────────┐
│                      PROCESSING PIPELINE                            │
│                                                                     │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────────────┐ │
│  │  Whisper    │   │  pyannote    │   │  Entity Extractor        │ │
│  │  (faster-   │→  │  Speaker     │→  │  (Claude API)            │ │
│  │  whisper)   │   │  Diarization │   │  People/Projects/        │ │
│  └─────────────┘   └──────────────┘   │  Decisions/Actions       │ │
│                                       └──────────────┬───────────┘ │
│                                                      │              │
│  ┌───────────────────────────────────────────────────▼───────────┐ │
│  │              Embedding Engine (nomic-embed-text-v1.5)         │ │
│  │              384-dim vectors, batch processing                │ │
│  └───────────────────────────────────────────────────┬───────────┘ │
└──────────────────────────────────────────────────────┼─────────────┘
                                                       │
                               ┌───────────────────────┼──────────────────────┐
                               │                       ▼                      │
                               │         MEMORY ENGINE / KNOWLEDGE GRAPH      │
                               │                                              │
                               │  ┌────────────────────────────────────────┐ │
                               │  │         PostgreSQL + pgvector           │ │
                               │  │                                        │ │
                               │  │  Relational:  Entities, Relationships  │ │
                               │  │  Vector:      Embeddings (384-dim)     │ │
                               │  │  Temporal:    Decision history, diffs  │ │
                               │  └────────────────────────────────────────┘ │
                               │                                              │
                               │  ┌─────────────┐   ┌──────────────────────┐ │
                               │  │    Redis    │   │  Pattern Detector    │ │
                               │  │   Cache     │   │  Contradiction Eng.  │ │
                               │  │   Sessions  │   │  Temporal Reasoner   │ │
                               │  └─────────────┘   └──────────────────────┘ │
                               └──────────────────────────────────────────────┘
```

### Service Topology

```
┌─────────────────────────────────────────────────────┐
│                   Docker Network                    │
│                                                     │
│  neva-api       neva-worker      neva-beat          │
│  (FastAPI)      (Celery)         (Celery scheduler) │
│      │               │                 │            │
│      └───────────────┴─────────────────┘            │
│                       │                             │
│              ┌────────┴──────────┐                  │
│              ▼                  ▼                   │
│         postgres             redis                  │
│         (port 5432)          (port 6379)            │
│                                                     │
│  neva-bot-manager   neva-voice                      │
│  (Recall.ai mgmt)   (ElevenLabs, Stage 4+)          │
└─────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack & Rationale

### Core Infrastructure

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Database | PostgreSQL 16 + pgvector | Single system for relational data and vector similarity search; avoids operational complexity of separate vector DB; pgvector supports HNSW indexing for fast ANN search |
| Cache / Queue broker | Redis 7 | Celery's most battle-tested broker; doubles as session cache and pub/sub for real-time dashboard updates |
| Async task runner | Celery 5 | Mature Python task queue, excellent retry logic, beat scheduler for cron-style tasks; native Redis integration |
| API framework | FastAPI | Async-native, Pydantic validation, automatic OpenAPI docs, WebSocket support for real-time meeting dashboards |
| Frontend | React + Vite | Fast builds, component ecosystem; no framework lock-in |

### Meeting Infrastructure

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Meeting bot hosting | Recall.ai | Handles the hardest part: reliable bot joining across Zoom/Meet/Teams without calendar integrations; $0.50/hr is cost-effective at scale; provides audio streams via webhook |
| Transcription (batch) | faster-whisper (large-v3) | 4x faster than openai-whisper on GPU; CTranslate2 backend; runs locally so no per-minute cost; word-level timestamps |
| Transcription (real-time) | Deepgram Nova-2 | $0.0125/min for streaming; 300ms latency; needed for Stage 4 voice turn detection where batch latency is unacceptable |
| Speaker diarization | pyannote/speaker-diarization-3.1 | State-of-the-art open source; integrates with faster-whisper for word-level speaker assignment; one-time Hugging Face access token |

### AI / ML

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Embeddings | nomic-embed-text-v1.5 | 384-dim (vs 1536 for OpenAI); 3x cheaper storage; competitive retrieval quality; runs locally on CPU, avoiding API costs for high-volume embedding |
| Extraction & Reasoning | Claude API (Haiku / Sonnet) | Haiku for entity extraction (cheap, fast); Sonnet for complex reasoning, contradiction detection, meeting summaries; structured JSON output via tool use |
| Voice synthesis | ElevenLabs | Best-in-class voice quality; voice cloning for consistent Neva identity; supports streaming for low-latency meeting participation (Stage 4+) |

### Rationale: Single DB vs. Separate Vector DB

Using Qdrant or Pinecone alongside PostgreSQL would require keeping two systems synchronized, managing dual connection pools, and handling failure modes where they drift apart. pgvector with HNSW indexing achieves sub-10ms p99 latency for 384-dim vectors up to ~10M rows — more than sufficient for organizational memory at scale. The relational joins between vector results and entity metadata become trivial with co-located data.

---

## 4. Database Schema

### Core Tables

```sql
-- Organizations and Users
CREATE TABLE organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    slug        TEXT UNIQUE NOT NULL,
    plan        TEXT NOT NULL DEFAULT 'starter',   -- starter, growth, enterprise
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    email           TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'member',  -- admin, member, viewer
    speaker_profile JSONB,                            -- voice fingerprint metadata
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Meetings
CREATE TABLE meetings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    recall_bot_id   TEXT,                            -- Recall.ai bot ID
    platform        TEXT NOT NULL,                   -- zoom, meet, teams, webex
    title           TEXT,
    scheduled_at    TIMESTAMPTZ,
    started_at      TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    duration_sec    INTEGER,
    participant_count INTEGER,
    status          TEXT NOT NULL DEFAULT 'scheduled',  -- scheduled, active, processing, complete, failed
    raw_audio_path  TEXT,                            -- S3/R2 object key
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_meetings_org_id ON meetings(org_id);
CREATE INDEX idx_meetings_started_at ON meetings(started_at DESC);

-- Transcripts
CREATE TABLE transcripts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id  UUID NOT NULL REFERENCES meetings(id),
    version     INTEGER NOT NULL DEFAULT 1,          -- 1=real-time, 2=batch corrected
    full_text   TEXT NOT NULL,
    word_count  INTEGER,
    language    TEXT DEFAULT 'en',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(meeting_id, version)
);

CREATE TABLE transcript_segments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transcript_id   UUID NOT NULL REFERENCES transcripts(id),
    speaker_id      UUID REFERENCES users(id),       -- NULL if unidentified
    speaker_label   TEXT,                            -- "Speaker 1" fallback
    start_ms        INTEGER NOT NULL,
    end_ms          INTEGER NOT NULL,
    text            TEXT NOT NULL,
    confidence      FLOAT,
    embedding       vector(384),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_segments_transcript ON transcript_segments(transcript_id);
CREATE INDEX idx_segments_embedding ON transcript_segments USING hnsw (embedding vector_cosine_ops);

-- Knowledge Graph: Entities
CREATE TABLE entities (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES organizations(id),
    type        TEXT NOT NULL,                       -- person, project, decision, action_item, topic, metric
    name        TEXT NOT NULL,
    canonical   TEXT NOT NULL,                       -- normalized form for deduplication
    description TEXT,
    metadata    JSONB DEFAULT '{}',
    embedding   vector(384),
    first_seen  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
    mention_count INTEGER NOT NULL DEFAULT 1,
    UNIQUE(org_id, type, canonical)
);

CREATE INDEX idx_entities_org_type ON entities(org_id, type);
CREATE INDEX idx_entities_embedding ON entities USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_entities_canonical ON entities(org_id, canonical text_pattern_ops);

-- Knowledge Graph: Relationships
CREATE TABLE entity_relationships (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    source_id       UUID NOT NULL REFERENCES entities(id),
    target_id       UUID NOT NULL REFERENCES entities(id),
    relationship    TEXT NOT NULL,                   -- owns, assigned_to, depends_on, contradicts, resolved_by, etc.
    confidence      FLOAT NOT NULL DEFAULT 1.0,
    evidence        TEXT,                            -- quote from transcript
    meeting_id      UUID REFERENCES meetings(id),
    valid_from      TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_until     TIMESTAMPTZ,                     -- NULL = still active
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_relationships_source ON entity_relationships(source_id);
CREATE INDEX idx_relationships_target ON entity_relationships(target_id);
CREATE INDEX idx_relationships_org ON entity_relationships(org_id, relationship);

-- Entity mentions per meeting (junction)
CREATE TABLE entity_mentions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID NOT NULL REFERENCES entities(id),
    meeting_id      UUID NOT NULL REFERENCES meetings(id),
    segment_id      UUID REFERENCES transcript_segments(id),
    context         TEXT,                            -- surrounding sentence
    mention_type    TEXT,                            -- introduced, updated, referenced, resolved
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mentions_entity ON entity_mentions(entity_id);
CREATE INDEX idx_mentions_meeting ON entity_mentions(meeting_id);

-- Decisions (specialized entity tracking)
CREATE TABLE decisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID NOT NULL REFERENCES entities(id),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    meeting_id      UUID NOT NULL REFERENCES meetings(id),
    statement       TEXT NOT NULL,
    rationale       TEXT,
    owner_id        UUID REFERENCES users(id),
    status          TEXT NOT NULL DEFAULT 'active',  -- active, revised, reversed, superseded
    confidence      FLOAT,
    superseded_by   UUID REFERENCES decisions(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Action Items
CREATE TABLE action_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID NOT NULL REFERENCES entities(id),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    meeting_id      UUID NOT NULL REFERENCES meetings(id),
    description     TEXT NOT NULL,
    assignee_id     UUID REFERENCES users(id),
    due_date        DATE,
    priority        TEXT DEFAULT 'medium',           -- low, medium, high, critical
    status          TEXT NOT NULL DEFAULT 'open',    -- open, in_progress, done, cancelled
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_action_items_assignee ON action_items(assignee_id, status);
CREATE INDEX idx_action_items_org_status ON action_items(org_id, status);

-- Meeting Summaries
CREATE TABLE meeting_summaries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id      UUID NOT NULL REFERENCES meetings(id) UNIQUE,
    tldr            TEXT NOT NULL,
    key_decisions   TEXT[] NOT NULL DEFAULT '{}',
    action_items    JSONB NOT NULL DEFAULT '[]',
    topics_covered  TEXT[] NOT NULL DEFAULT '{}',
    sentiment       TEXT,                            -- positive, neutral, tense, productive
    follow_up_needed BOOLEAN DEFAULT false,
    embedding       vector(384),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_summaries_embedding ON meeting_summaries USING hnsw (embedding vector_cosine_ops);

-- Contradiction Log
CREATE TABLE contradictions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    entity_id_a     UUID NOT NULL REFERENCES entities(id),
    entity_id_b     UUID NOT NULL REFERENCES entities(id),
    description     TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'low',     -- low, medium, high
    status          TEXT NOT NULL DEFAULT 'open',    -- open, acknowledged, resolved
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);

-- Neva's message log (for Slack/Teams and meeting voice)
CREATE TABLE neva_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    meeting_id      UUID REFERENCES meetings(id),
    channel         TEXT NOT NULL,                   -- slack, teams, meeting_voice, email
    channel_ref     TEXT,                            -- Slack thread_ts, Teams conversation_id
    direction       TEXT NOT NULL,                   -- inbound, outbound
    content         TEXT NOT NULL,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### pgvector Configuration

```sql
-- Enable extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- for text search on entity names

-- HNSW index tuning (at index creation)
-- m=16, ef_construction=64 is a good default for 384-dim
-- Tune ef_search at query time: SET hnsw.ef_search = 100;
```

---

## 5. API Design

### Authentication

All endpoints require a valid JWT in the `Authorization: Bearer <token>` header, except `/api/auth/*`. JWTs encode `user_id`, `org_id`, and `role`.

### Key Endpoints

```
POST   /api/auth/login
POST   /api/auth/refresh
DELETE /api/auth/logout

GET    /api/meetings                         # list meetings for org
POST   /api/meetings                         # schedule / register a meeting
GET    /api/meetings/{id}                    # meeting detail
GET    /api/meetings/{id}/transcript         # full transcript with speaker labels
GET    /api/meetings/{id}/summary            # AI-generated summary
GET    /api/meetings/{id}/action-items       # extracted action items
GET    /api/meetings/{id}/decisions          # decisions logged this meeting
GET    /api/meetings/{id}/entities           # entities mentioned

POST   /api/bot/join                         # instruct Recall.ai bot to join a meeting URL
POST   /api/bot/leave                        # remove bot from meeting
GET    /api/bot/status/{recall_bot_id}       # real-time bot status

GET    /api/memory/search?q=&type=           # semantic + keyword search across org memory
GET    /api/memory/entities                  # list all entities (filterable by type)
GET    /api/memory/entities/{id}             # entity detail with relationship graph
GET    /api/memory/entities/{id}/history     # how this entity evolved over meetings
GET    /api/memory/decisions                 # all active decisions
GET    /api/memory/contradictions            # detected contradictions

POST   /api/ask                              # freeform question to Neva (RAG-grounded answer)
GET    /api/ask/history                      # past Q&A log

GET    /api/actions                          # all open action items across org
PATCH  /api/actions/{id}                     # update status
GET    /api/actions/by-person/{user_id}      # action items for a specific person

POST   /api/integrations/slack/webhook       # inbound Slack events
POST   /api/integrations/teams/webhook       # inbound Teams events
GET    /api/integrations/status              # which integrations are configured

WS     /ws/meetings/{id}/live                # real-time transcript stream (Stage 1+)
WS     /ws/meetings/{id}/voice               # bidirectional audio for Stage 4+

GET    /api/org/members                      # team roster
GET    /api/org/stats                        # meeting cadence, memory size, coverage
```

### Request / Response Patterns

```python
# POST /api/ask — example
# Request
{
  "question": "What did we decide about the Q2 roadmap prioritization?",
  "context_meeting_ids": ["uuid-optional"],  # optional scope
  "max_sources": 5
}

# Response
{
  "answer": "In the March 3rd planning meeting, the team decided to prioritize...",
  "confidence": 0.87,
  "sources": [
    {
      "meeting_id": "uuid",
      "meeting_title": "Q2 Planning",
      "meeting_date": "2026-03-03",
      "segment": "We're going to put the analytics dashboard first...",
      "speaker": "Sarah Chen",
      "relevance_score": 0.94
    }
  ],
  "related_decisions": ["uuid-of-decision-entity"],
  "contradictions": []
}
```

```python
# POST /api/bot/join — example
# Request
{
  "meeting_url": "https://zoom.us/j/...",
  "platform": "zoom",
  "meeting_title": "Engineering Standup",
  "scheduled_at": "2026-03-10T14:00:00Z"
}

# Response
{
  "meeting_id": "uuid",
  "recall_bot_id": "bot_xxx",
  "status": "joining",
  "estimated_join_time": "2026-03-10T14:00:30Z"
}
```

### Webhook: Recall.ai Inbound

```python
# POST /api/internal/recall-webhook (Recall.ai calls this)
{
  "event": "bot.status_change",            # or transcript.chunk, recording.complete
  "bot_id": "bot_xxx",
  "data": {
    "status": "in_call",
    "participant_count": 8
  }
}
```

---

## 6. Processing Pipeline

### Audio to Knowledge Graph: Full Pipeline

```
Recall.ai Bot
     │
     │  (audio stream or recording webhook)
     ▼
┌────────────────────────────────────────────────┐
│  STAGE A: Audio Ingestion                      │
│                                                │
│  1. Recall webhook fires → Celery task queued  │
│  2. Download audio from Recall CDN → R2/S3     │
│  3. Validate audio integrity, extract metadata │
└────────────────────┬───────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│  STAGE B: Transcription                        │
│                                                │
│  faster-whisper large-v3 (batch, local GPU)    │
│  OR Deepgram Nova-2 (real-time streaming)      │
│                                                │
│  Output: word-level segments with timestamps   │
│  [{word, start_ms, end_ms, confidence}, ...]   │
└────────────────────┬───────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│  STAGE C: Speaker Diarization                  │
│                                                │
│  pyannote/speaker-diarization-3.1              │
│  Input: audio file                             │
│  Output: [{speaker: "SPEAKER_00",              │
│            start: 0.0, end: 12.4}, ...]        │
│                                                │
│  Merge with transcript segments by timestamp   │
│  → each segment gets speaker_label             │
│                                                │
│  Speaker ID resolution:                        │
│  1. Check speaker_profiles in users table      │
│  2. Cluster diarization embeddings vs known    │
│  3. Fall back to "Speaker 1", "Speaker 2"      │
└────────────────────┬───────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│  STAGE D: Segment Embedding                    │
│                                                │
│  nomic-embed-text-v1.5 (local, batched)        │
│  Embed each segment (~3-5 sentences each)      │
│  384-dim vectors → transcript_segments table   │
│                                                │
│  Also embed full meeting text for summary vec  │
└────────────────────┬───────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│  STAGE E: Entity Extraction (Claude Haiku)     │
│                                                │
│  Process transcript in 2000-token chunks       │
│  with 200-token overlap                        │
│                                                │
│  Prompt: extract structured entities           │
│  Tool use → guaranteed JSON output             │
│                                                │
│  Entities extracted:                           │
│  - People (name, role, org context)            │
│  - Projects (name, status, owner)              │
│  - Decisions (statement, rationale, owner)     │
│  - Action Items (task, assignee, due date)     │
│  - Topics (theme, sentiment)                   │
│  - Metrics (name, value, trend)                │
└────────────────────┬───────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│  STAGE F: Entity Resolution & Deduplication    │
│                                                │
│  For each extracted entity:                    │
│  1. Normalize canonical form                   │
│  2. Vector similarity search in entities table │
│     (cosine similarity > 0.92 = same entity)   │
│  3. Fuzzy string match on canonical names      │
│  4. UPSERT: new entity or merge into existing  │
│  5. Update mention_count, last_seen            │
└────────────────────┬───────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│  STAGE G: Relationship Extraction              │
│                                                │
│  Claude Haiku: given entity list + transcript  │
│  Extract relationships between entity pairs:   │
│  - Person owns/assigned_to Project             │
│  - Decision depends_on Decision                │
│  - Action Item blocks Project                  │
│  - Person mentioned Topic                      │
│                                                │
│  Write to entity_relationships with evidence   │
└────────────────────┬───────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│  STAGE H: Contradiction Detection              │
│                                                │
│  Claude Sonnet (run on new decisions only)     │
│  Compare new decisions vs. recent active ones  │
│  via vector search (top-20 similar decisions)  │
│                                                │
│  Prompt: do these conflict? rate severity      │
│  Write contradictions to contradictions table  │
│  Tag conflicting entity_relationships          │
└────────────────────┬───────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│  STAGE I: Summary Generation (Claude Sonnet)   │
│                                                │
│  Input: full transcript + extracted entities   │
│  Output:                                       │
│  - TL;DR (2-3 sentences)                       │
│  - Key decisions list                          │
│  - Action items with owners and due dates      │
│  - Topics covered                              │
│  - Meeting sentiment                           │
│  - Follow-up meeting needed? (bool)            │
│                                                │
│  Embed summary → meeting_summaries table       │
└────────────────────┬───────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────┐
│  STAGE J: Notifications                        │
│                                                │
│  - Slack: post summary to configured channel   │
│  - Email: send action item assignments         │
│  - Dashboard: WebSocket push to active clients │
│  - Flag contradictions for review              │
└────────────────────────────────────────────────┘
```

### Pipeline Timing (per 60-minute meeting)

| Stage | Duration | Notes |
|-------|----------|-------|
| A: Audio download | ~30s | Depends on recording size (~150MB for 1hr) |
| B: Transcription | ~3-5 min | faster-whisper on GPU; 12-15x realtime |
| C: Diarization | ~2-3 min | pyannote runs on CPU |
| D: Embedding | ~30s | Batched, ~200 segments |
| E: Extraction | ~2-3 min | Multiple Claude Haiku calls |
| F: Resolution | ~15s | DB queries + vector search |
| G: Relationships | ~1 min | Claude Haiku |
| H: Contradictions | ~30s | Claude Sonnet, scoped query |
| I: Summary | ~20s | Claude Sonnet, single call |
| J: Notifications | ~5s | Async HTTP calls |
| **Total** | **~12-16 min** | Post-meeting latency |

---

## 7. Memory Engine & Knowledge Graph

### Design Principles

**Temporal Integrity.** Entities do not get overwritten — they accumulate history. When a decision is revised, the old decision is marked `status='revised'` and `superseded_by` points to the new one. This preserves the full audit trail.

**Confidence-Weighted Relationships.** Every relationship carries a confidence score (0.0-1.0) derived from: how explicitly stated it was, whether multiple speakers confirmed it, and recency decay for old inferences.

**Vector + Relational Hybrid Search.** The `/api/ask` endpoint uses a two-phase retrieval:
1. Dense retrieval: `SELECT ... ORDER BY embedding <=> query_embedding LIMIT 50`
2. Reranking: BM25 keyword score blended with vector similarity
3. Graph expansion: pull entity relationships for top-5 results to get adjacent context

### Contradiction Detection Algorithm

```python
async def detect_contradictions(new_decision: Decision, org_id: UUID):
    # 1. Embed new decision statement
    query_vec = embed(new_decision.statement)

    # 2. Find semantically similar active decisions
    candidates = await db.fetch("""
        SELECT d.*, e.embedding
        FROM decisions d
        JOIN entities e ON e.id = d.entity_id
        WHERE d.org_id = $1
          AND d.status = 'active'
          AND d.id != $2
        ORDER BY e.embedding <=> $3
        LIMIT 20
    """, org_id, new_decision.id, query_vec)

    if not candidates:
        return

    # 3. Ask Claude to evaluate contradictions
    prompt = build_contradiction_prompt(new_decision, candidates)
    result = await claude.haiku(prompt, tools=[ContradictionTool])

    # 4. Log confirmed contradictions
    for contradiction in result.contradictions:
        if contradiction.confidence > 0.7:
            await log_contradiction(contradiction)
```

### Pattern Detection (runs nightly via Celery Beat)

- **Recurring topics**: entities mentioned in 3+ consecutive meetings → tag as `recurring`
- **Stale action items**: open items > 7 days past due → escalation candidates
- **Decision velocity**: rate of new decisions vs. reversals (org health signal)
- **Meeting load**: who attends the most meetings (fatigue detection)
- **Knowledge gaps**: topics discussed but no decision or owner attached

### Entity Embedding Strategy

Entities are embedded from a composite string to maximize semantic density:

```python
def entity_to_embed_string(entity: Entity) -> str:
    parts = [f"{entity.type}: {entity.name}"]
    if entity.description:
        parts.append(entity.description)
    if entity.metadata.get("aliases"):
        parts.append("also known as: " + ", ".join(entity.metadata["aliases"]))
    return " | ".join(parts)
```

---

## 8. Growth Stage Implementation

### Stage 1: Silent Observer (MVP)

Core loop: join → transcribe → extract → embed → store.

- Recall.ai bot joins via URL, no calendar integration needed
- faster-whisper runs on same server as API (GPU preferred, CPU fallback)
- All outputs stored, no external notifications yet
- Dashboard shows live transcript via WebSocket

Implementation: `bot_manager.py`, `pipeline/transcriber.py`, `pipeline/extractor.py`, `pipeline/memory_writer.py`

### Stage 2: Post-Meeting Analyst

Trigger: pipeline completion webhook.

- Generate and store summary (Claude Sonnet)
- Format action items, send to assignees via email
- Optional Slack post to `#meeting-notes` channel
- Dashboard summary view

New components: `notifier/slack.py`, `notifier/email.py`, `summarizer.py`

### Stage 3: Async Team Member

Neva joins Slack/Teams as a bot user and listens for:
- Direct mentions: `@neva what did we decide about X?`
- Channel keywords: `neva help`, `neva find`
- Slash command: `/neva ask ...`

Answer pipeline: question → embed → hybrid retrieval → Claude Sonnet with RAG context → response.

New components: `integrations/slack_bot.py`, `integrations/teams_bot.py`, `qa/retriever.py`, `qa/answerer.py`

### Stage 4: Active Participant

Real-time audio path with Deepgram for live transcription.

Turn detection: Neva monitors the live transcript for:
- Direct address: "Neva, what do we know about..."
- Natural break (2s silence after a question)
- Pre-configured trigger phrases

Voice synthesis: ElevenLabs streaming TTS → Recall.ai injects audio into meeting.

Constraint management:
- Max 1 Neva interjection per 5 minutes unless directly addressed
- Never interrupt — wait for complete pause
- Configurable verbosity level per org (quiet / balanced / proactive)

New components: `voice/turn_detector.py`, `voice/synthesizer.py`, `voice/meeting_speaker.py`

### Stage 5: Autonomous PM

Proactive behaviors (all configurable, all require org admin opt-in):

- Pre-meeting brief: "Here's what's been decided about this project, open action items, and suggested agenda items."
- Represent absent members: "Alex mentioned in last week's meeting that she prefers option B because..."
- Draft follow-up PRDs: "Based on the discussion, I've drafted a requirements doc. Review link: ..."
- Escalate stale items: "The authentication decision from Feb 20th hasn't been actioned. Should I schedule a follow-up?"

New components: `pm/briefer.py`, `pm/drafter.py`, `pm/escalator.py`, `pm/representative.py`

---

## 9. Deployment Architecture

### Development: Docker Compose

```yaml
# docker-compose.yml
version: "3.9"

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://neva:neva@postgres:5432/neva
      - REDIS_URL=redis://redis:6379/0
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - RECALL_API_KEY=${RECALL_API_KEY}
      - ELEVENLABS_API_KEY=${ELEVENLABS_API_KEY}
    depends_on:
      - postgres
      - redis
    volumes:
      - ./:/app
    command: uvicorn neva.main:app --reload --host 0.0.0.0 --port 8000

  worker:
    build: .
    environment:
      - DATABASE_URL=postgresql://neva:neva@postgres:5432/neva
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    command: celery -A neva.tasks worker --loglevel=info --concurrency=4
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]             # for faster-whisper

  beat:
    build: .
    environment:
      - DATABASE_URL=postgresql://neva:neva@postgres:5432/neva
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
    command: celery -A neva.tasks beat --loglevel=info

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: neva
      POSTGRES_PASSWORD: neva
      POSTGRES_DB: neva
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./migrations/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=http://localhost:8000

volumes:
  pgdata:
```

### Production: Kubernetes

```
┌─────────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster (EKS / GKE)               │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Ingress (nginx / AWS ALB)                              │   │
│  │  TLS termination, rate limiting, WAF                    │   │
│  └─────────────────────┬───────────────────────────────────┘   │
│                        │                                        │
│        ┌───────────────┼───────────────┐                       │
│        ▼               ▼               ▼                       │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐               │
│  │ api      │   │ frontend │   │ bot-manager  │               │
│  │ Deployment│   │ Deployment│   │ Deployment   │               │
│  │ 3 replicas│   │ 2 replicas│   │ 2 replicas   │               │
│  └──────────┘   └──────────┘   └──────────────┘               │
│                                                                 │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────────┐  │
│  │ worker       │   │ beat         │   │ voice-worker       │  │
│  │ Deployment   │   │ Deployment   │   │ (Stage 4+)         │  │
│  │ 4 replicas   │   │ 1 replica    │   │ GPU node pool      │  │
│  │ (CPU nodes)  │   │              │   │ 2 replicas         │  │
│  └──────────────┘   └──────────────┘   └────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Managed Services (outside cluster)                      │  │
│  │                                                          │  │
│  │  RDS PostgreSQL + pgvector   ElastiCache Redis           │  │
│  │  S3 / Cloudflare R2          CloudWatch Logs             │  │
│  │  (audio storage)             Prometheus + Grafana        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Kubernetes Configs

```yaml
# HorizontalPodAutoscaler for API
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: neva-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: neva-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 65
    - type: External
      external:
        metric:
          name: redis_queue_length
        target:
          type: AverageValue
          averageValue: "50"
```

### CI/CD Pipeline

```
GitHub Push (main)
       │
       ▼
GitHub Actions
  ├── pytest (unit + integration)
  ├── ruff + mypy lint
  ├── docker build + push to ECR
  └── kubectl rollout (with rollback on failure)
```

---

## 10. Cost Analysis

### Per-User Per-Month Cost Model

Assumptions: 1 user attends 8 meetings/month, avg 45 minutes each = 6 hours of meeting audio/month.

#### Stage 1-2 (Silent Observer + Analyst)

| Component | Usage | Unit Cost | Monthly Cost |
|-----------|-------|-----------|--------------|
| Recall.ai bot | 6 hrs/user | $0.50/hr | $3.00 |
| faster-whisper (local GPU) | 6 hrs audio | ~$0.02/hr GPU time | $0.12 |
| Claude Haiku (extraction) | ~50K tokens | $0.25/M input, $1.25/M output | $0.03 |
| Claude Sonnet (summaries) | ~15K tokens | $3/M input, $15/M output | $0.06 |
| nomic-embed-text (local) | ~200 segments | effectively $0 | $0.00 |
| PostgreSQL storage | ~5MB/user/mo | $0.023/GB | $0.00 |
| Redis | shared | amortized | $0.02 |
| S3/R2 audio | ~900MB/user | $0.015/GB | $0.01 |
| **Total (per user)** | | | **~$3.24** |

At scale, Recall.ai dominates. With volume discounts on Recall.ai (~$0.30/hr at enterprise) and Claude API credits, this drops to approximately **$1.85/user/month**.

#### Stage 3 (Async Team Member) — additive

| Component | Usage | Unit Cost | Monthly Cost |
|-----------|-------|-----------|--------------|
| Claude Haiku (Q&A answers) | ~30 queries/user | $0.25/M tokens | $0.02 |
| Slack API | free tier | $0 | $0.00 |
| **Stage 3 addition** | | | **~$0.02** |

#### Stage 4 (Active Participant) — additive

| Component | Usage | Unit Cost | Monthly Cost |
|-----------|-------|-----------|--------------|
| Deepgram (real-time) | 6 hrs | $0.0125/min = $0.75/hr | $4.50 |
| ElevenLabs | ~10 utterances/meeting | $0.18/1K chars, ~100 chars each | $1.44 |
| **Stage 4 addition** | | | **~$5.94** |

Stage 4 is significantly more expensive due to real-time transcription. Price real-time participation as a premium tier.

### Pricing Strategy

| Tier | Included | Price |
|------|----------|-------|
| Observer | Stage 1-2, up to 10 users | $29/mo |
| Team | Stage 1-3, unlimited users | $8/user/mo |
| Voice | Stage 1-4, unlimited users | $18/user/mo |
| PM | Stage 1-5, enterprise | custom |

**Gross margin at scale (Team tier):** $8 - $1.85 = $6.15/user/mo = ~77% margin.

---

## 11. MVP Scope & Timeline

### MVP Definition: Stage 1 (Silent Observer)

The MVP proves the core loop works reliably: bot joins, transcribes accurately, extracts entities, builds memory, surfaces it in a dashboard.

MVP is NOT: voice, Slack integration, Q&A, autonomous PM.

### 8-Week Timeline

```
Week 1-2: Foundation
  ├── PostgreSQL schema + pgvector setup
  ├── FastAPI skeleton + JWT auth
  ├── Recall.ai bot integration (join/leave/webhook)
  └── Basic React dashboard shell

Week 3-4: Transcription Pipeline
  ├── faster-whisper integration + Celery task
  ├── pyannote speaker diarization
  ├── Segment storage + transcript viewer in dashboard
  └── Webhook → task queue flow

Week 5-6: Memory Engine
  ├── nomic-embed-text embedding pipeline
  ├── Entity extraction (Claude Haiku) + entity tables
  ├── Entity resolution + deduplication
  └── Relationship extraction

Week 7: Knowledge Graph UI + Search
  ├── /api/memory/search endpoint (hybrid retrieval)
  ├── Entity detail pages in dashboard
  ├── Meeting summary generation (Claude Sonnet)
  └── Contradiction detection (basic version)

Week 8: Polish + Launch Prep
  ├── Error handling + retry logic throughout pipeline
  ├── End-to-end test with real meetings
  ├── Kubernetes deployment + monitoring
  ├── Onboarding flow (org creation, bot invite instructions)
  └── Billing integration (Stripe)
```

### MVP Success Metrics

- Bot successfully joins and captures audio for ≥95% of meeting join attempts
- Transcription WER ≤ 15% on clean audio
- Entity extraction precision ≥ 80% (manual sample evaluation)
- Pipeline completes within 20 minutes of meeting end
- Dashboard loads meeting summary within 500ms (cached)

### Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Recall.ai reliability issues | Low | High | Fallback: Google Meet native recording API |
| faster-whisper accuracy on noisy audio | Medium | Medium | Deepgram as fallback; audio preprocessing (noise reduction) |
| Entity extraction hallucination | Medium | Medium | Confidence thresholds; human review queue for low-confidence extractions |
| pgvector performance at scale | Low | High | HNSW index tuning; partition by org_id at 1M+ entities |
| pyannote diarization accuracy on large calls (15+ speakers) | High | Medium | Cap at 10 speaker labels; cluster remainder as "Other" |

---

## 12. Scalability Considerations

### Database Scaling

**Partitioning strategy** (activate at ~1M meetings):

```sql
-- Partition transcript_segments by created_at (monthly)
CREATE TABLE transcript_segments (
    ...
) PARTITION BY RANGE (created_at);

CREATE TABLE transcript_segments_2026_03
    PARTITION OF transcript_segments
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
```

**Entity table** grows proportionally to org count, not meeting count. Index on `(org_id, type, canonical)` keeps lookups O(log n) per org.

**pgvector at scale**: HNSW index degrades gracefully to ~20ms at 10M vectors. Beyond that, consider partitioning vectors by entity type and using approximate nearest-neighbor with a pre-filter.

### Celery Worker Scaling

Different task types have very different resource profiles:

```python
# celery app configuration
app.conf.task_routes = {
    "neva.tasks.transcribe": {"queue": "gpu"},        # GPU nodes
    "neva.tasks.diarize": {"queue": "cpu_heavy"},     # high CPU
    "neva.tasks.extract_entities": {"queue": "io"},   # network-bound (Claude API)
    "neva.tasks.embed": {"queue": "cpu_heavy"},
    "neva.tasks.summarize": {"queue": "io"},
    "neva.tasks.notify": {"queue": "default"},
}
```

Maintain separate node pools for GPU (transcription/embedding) and CPU/IO (extraction/notification). This allows each to scale independently.

### Multi-Tenancy Isolation

At the application layer, every query is scoped by `org_id`. At scale, consider:

- **Row-level security** in PostgreSQL for defense-in-depth
- **Separate Redis key namespaces** per org (prefix `org:{id}:*`)
- **Rate limiting** per org on Celery task submission to prevent a single large org from starving others

### Audio Storage

Audio files are write-once, read-rarely (only during reprocessing). Use Cloudflare R2 (zero egress fees) with lifecycle policies to move files older than 90 days to Glacier-class storage, and delete raw audio after 1 year (keep transcripts).

### Embedding Model Serving

At >10,000 meetings/month, running nomic-embed-text locally on a shared worker becomes a bottleneck. Options:

1. **Dedicated embedding worker pods** with CPU optimization (ONNX Runtime)
2. **Batch accumulation**: buffer segments for 30s before embedding (reduces model load calls 10x)
3. **Voyager (Meta) or Chroma's hosted embedding** as a managed alternative if self-hosting becomes operationally complex

### Realtime Path (Stage 4) Isolation

The real-time voice path (Deepgram + ElevenLabs + turn detection) must never be blocked by batch pipeline jobs. Keep these on a completely separate Celery queue with dedicated workers and a separate Redis instance to avoid head-of-line blocking.

```
Batch pipeline  ──→  Redis instance A  ──→  Worker pool A (CPU/GPU)
Realtime voice  ──→  Redis instance B  ──→  Worker pool B (low-latency, reserved)
```

### Observability Stack

```
Structured Logging (JSON) → CloudWatch / Loki
Metrics (Prometheus) → Grafana dashboards
  - pipeline stage latency (p50, p95, p99)
  - Celery queue depth per queue
  - Claude API token consumption by org
  - pgvector query latency by index
Tracing (OpenTelemetry) → Jaeger / Tempo
  - full trace from Recall webhook → notification sent
Alerting:
  - pipeline stuck > 30min → PagerDuty
  - Recall bot join failure rate > 5% → PagerDuty
  - Claude API error rate > 1% → Slack alert
```

---

## Appendix A: Directory Structure

```
neva/
├── neva/
│   ├── main.py                    # FastAPI app factory
│   ├── config.py                  # Settings (pydantic-settings)
│   ├── db.py                      # AsyncPG connection pool
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── meeting.py
│   │   ├── entity.py
│   │   ├── transcript.py
│   │   └── user.py
│   ├── api/                       # FastAPI routers
│   │   ├── meetings.py
│   │   ├── memory.py
│   │   ├── ask.py
│   │   ├── actions.py
│   │   ├── bot.py
│   │   └── integrations.py
│   ├── pipeline/                  # Core processing pipeline
│   │   ├── transcriber.py         # faster-whisper wrapper
│   │   ├── diarizer.py            # pyannote wrapper
│   │   ├── embedder.py            # nomic-embed-text
│   │   ├── extractor.py           # Claude Haiku entity extraction
│   │   ├── resolver.py            # entity deduplication
│   │   ├── relationships.py       # relationship extraction
│   │   ├── contradictions.py      # contradiction detection
│   │   └── summarizer.py         # Claude Sonnet summaries
│   ├── memory/                    # Knowledge graph queries
│   │   ├── retriever.py           # hybrid search
│   │   ├── graph.py               # relationship traversal
│   │   └── patterns.py            # pattern detection
│   ├── bot/                       # Recall.ai management
│   │   ├── manager.py
│   │   └── webhook_handler.py
│   ├── voice/                     # Stage 4+
│   │   ├── turn_detector.py
│   │   └── synthesizer.py
│   ├── integrations/              # Stage 3+
│   │   ├── slack.py
│   │   └── teams.py
│   ├── tasks.py                   # Celery task definitions
│   └── notifier.py
├── frontend/                      # React + Vite
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Meeting.tsx
│   │   │   ├── Memory.tsx
│   │   │   └── Ask.tsx
│   │   └── components/
├── migrations/                    # Alembic
├── tests/
├── docker-compose.yml
├── docker-compose.prod.yml
└── k8s/
    ├── api-deployment.yaml
    ├── worker-deployment.yaml
    ├── hpa.yaml
    └── ingress.yaml
```

---

## Appendix B: Claude Extraction Prompt Structure

```python
ENTITY_EXTRACTION_SYSTEM = """
You are an expert at extracting structured knowledge from meeting transcripts.
Extract all entities with precision. Do not hallucinate entities not explicitly
mentioned. When uncertain, lower the confidence score rather than omitting.

Always use the extract_entities tool to return structured output.
"""

ENTITY_EXTRACTION_TOOL = {
    "name": "extract_entities",
    "description": "Extract all entities from the meeting transcript chunk",
    "input_schema": {
        "type": "object",
        "properties": {
            "people": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                        "organization": {"type": "string"},
                        "confidence": {"type": "number"}
                    }
                }
            },
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "statement": {"type": "string"},
                        "rationale": {"type": "string"},
                        "owner": {"type": "string"},
                        "confidence": {"type": "number"},
                        "evidence_quote": {"type": "string"}
                    }
                }
            },
            "action_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "assignee": {"type": "string"},
                        "due_date": {"type": "string"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                        "confidence": {"type": "number"}
                    }
                }
            },
            "projects": {"type": "array"},
            "topics": {"type": "array"}
        }
    }
}
```
