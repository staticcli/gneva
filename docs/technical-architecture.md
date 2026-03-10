# Kura Technical Architecture

**Version:** 1.0
**Date:** 2026-03-10

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  React Web   │  │  Slack Bot   │  │  Teams Bot               │  │
│  │  Dashboard   │  │  @Kura       │  │  @Kura                   │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘  │
│         │                 │                      │                  │
│         └────────────────┬┴──────────────────────┘                  │
│                          │ HTTPS / WebSocket                        │
├──────────────────────────┼──────────────────────────────────────────┤
│                    API GATEWAY                                      │
│  ┌───────────────────────┴─────────────────────────────────────┐   │
│  │  FastAPI  (auth, rate limiting, CORS, request routing)      │   │
│  └───────────────────────┬─────────────────────────────────────┘   │
├──────────────────────────┼──────────────────────────────────────────┤
│                    SERVICE LAYER                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Meeting     │  │  Memory      │  │  Query                   │  │
│  │  Service     │  │  Engine      │  │  Engine                  │  │
│  │              │  │              │  │                          │  │
│  │  - Bot mgmt  │  │  - Entity    │  │  - @Kura chat            │  │
│  │  - Audio     │  │    extraction│  │  - Semantic search       │  │
│  │  - Transcript│  │  - Knowledge │  │  - Context assembly      │  │
│  │  - Diarize   │  │    graph     │  │  - Answer generation     │  │
│  │  - Summarize │  │  - Temporal  │  │                          │  │
│  └──────┬───────┘  │    reasoning │  └──────────┬───────────────┘  │
│         │          └──────┬───────┘              │                  │
├─────────┼─────────────────┼─────────────────────┼──────────────────┤
│         │           ASYNC WORKERS                │                  │
│  ┌──────┴───────────┐  ┌──────┴──────────────────┴──────────────┐  │
│  │  Celery Workers  │  │  Background Tasks                      │  │
│  │  - transcribe    │  │  - entity_extraction                   │  │
│  │  - diarize       │  │  - contradiction_detection             │  │
│  │  - summarize     │  │  - pattern_analysis                    │  │
│  │  - embed         │  │  - brief_generation                    │  │
│  └──────┬───────────┘  └──────┬─────────────────────────────────┘  │
├─────────┼─────────────────────┼─────────────────────────────────────┤
│         │           DATA LAYER                                      │
│  ┌──────┴──────────────────┴─────────────────────────────────────┐  │
│  │  PostgreSQL + pgvector                                        │  │
│  │  ┌─────────────┐ ┌───────────┐ ┌───────────┐ ┌────────────┐  │  │
│  │  │ Relational  │ │  Vector   │ │  Meeting  │ │  Knowledge │  │  │
│  │  │ (users,orgs)│ │  (embeds) │ │  (trans-  │ │  Graph     │  │  │
│  │  │             │ │  384-dim  │ │  cripts)  │ │  (entities)│  │  │
│  │  └─────────────┘ └───────────┘ └───────────┘ └────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐                                │
│  │  Redis       │  │  S3 / R2    │                                 │
│  │  (cache,     │  │  (audio     │                                 │
│  │   queues)    │  │   storage)  │                                 │
│  └──────────────┘  └──────────────┘                                │
├────────────────────────────────────────────────────────────────────┤
│                    EXTERNAL SERVICES                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  Recall.ai   │  │  Claude API  │  │  ElevenLabs             │  │
│  │  (meeting    │  │  (reasoning, │  │  (voice synthesis,      │  │
│  │   bots)      │  │   extraction)│  │   Stage 4+)             │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

---

## 2. Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| **Backend** | FastAPI (Python 3.12) | Async-native, type hints, auto OpenAPI docs |
| **Frontend** | React 18 + TypeScript | Component model, ecosystem, hiring pool |
| **Database** | PostgreSQL 16 + pgvector | Single DB for relational + vector, reduces ops |
| **Cache/Queue** | Redis 7 | Celery broker, session cache, rate limiting |
| **Task Queue** | Celery | Distributed async processing, battle-tested |
| **Meeting Bots** | Recall.ai API | Cross-platform (Zoom/Teams/Meet), $0.50/hr |
| **Transcription** | faster-whisper (local) | Free, good accuracy, runs on GPU |
| **Diarization** | pyannote 3.x | Best open-source speaker diarization |
| **Embeddings** | nomic-embed-text-v1.5 | 384-dim, runs locally, good quality |
| **LLM** | Claude API (Sonnet) | Best at structured extraction, reasoning |
| **Voice (Stage 4)** | ElevenLabs Conv AI | Sub-300ms latency, turn-taking model |
| **Object Storage** | Cloudflare R2 / S3 | Audio file storage, encrypted at rest |
| **Deployment** | Docker Compose (dev), K8s (prod) | Standard, scalable |

---

## 3. Database Schema

### Core Tables

```sql
-- Multi-tenant organizations
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    plan VARCHAR(20) DEFAULT 'free',  -- free, pro, team, enterprise
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),
    oauth_provider VARCHAR(50),
    oauth_id VARCHAR(255),
    role VARCHAR(20) DEFAULT 'member',  -- admin, member, viewer
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Calendar integrations
CREATE TABLE calendar_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(20) NOT NULL,  -- google, outlook
    access_token TEXT NOT NULL,  -- encrypted
    refresh_token TEXT NOT NULL,  -- encrypted
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Meetings
CREATE TABLE meetings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    calendar_event_id VARCHAR(255),
    title VARCHAR(500),
    platform VARCHAR(20),  -- zoom, teams, meet
    meeting_url TEXT,
    bot_id VARCHAR(255),  -- Recall.ai bot ID
    status VARCHAR(20) DEFAULT 'scheduled',  -- scheduled, recording, processing, ready, failed
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    audio_url TEXT,  -- S3/R2 URL (encrypted)
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Meeting participants
CREATE TABLE meeting_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id UUID REFERENCES meetings(id) ON DELETE CASCADE,
    person_id UUID REFERENCES people(id),
    speaker_label VARCHAR(50),  -- pyannote speaker ID
    speaking_time_seconds INTEGER DEFAULT 0,
    is_host BOOLEAN DEFAULT FALSE
);

-- Transcript segments (speaker-attributed)
CREATE TABLE transcript_segments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id UUID REFERENCES meetings(id) ON DELETE CASCADE,
    speaker_label VARCHAR(50),
    person_id UUID REFERENCES people(id),
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    text TEXT NOT NULL,
    confidence FLOAT,
    embedding vector(384)  -- pgvector, for semantic search
);

-- Full meeting summaries
CREATE TABLE meeting_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id UUID REFERENCES meetings(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    key_points JSONB,  -- [{point, speaker, timestamp}]
    generated_by VARCHAR(50) DEFAULT 'claude-sonnet',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Knowledge Graph Tables

```sql
-- People (entity)
CREATE TABLE people (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    role VARCHAR(255),
    department VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    embedding vector(384)
);

-- Projects (entity)
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',
    first_mentioned_at TIMESTAMPTZ,
    last_mentioned_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    embedding vector(384)
);

-- Decisions (entity, temporal)
CREATE TABLE decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    meeting_id UUID REFERENCES meetings(id),
    description TEXT NOT NULL,
    context TEXT,
    decided_by UUID REFERENCES people(id),
    status VARCHAR(20) DEFAULT 'active',  -- active, superseded, reversed
    superseded_by UUID REFERENCES decisions(id),
    decided_at TIMESTAMPTZ,
    confidence FLOAT DEFAULT 1.0,
    embedding vector(384)
);

-- Action items (entity, trackable)
CREATE TABLE action_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    meeting_id UUID REFERENCES meetings(id),
    description TEXT NOT NULL,
    assignee_id UUID REFERENCES people(id),
    due_date DATE,
    status VARCHAR(20) DEFAULT 'open',  -- open, completed, cancelled, overdue
    completed_at TIMESTAMPTZ,
    source_timestamp_ms INTEGER,  -- where in the meeting
    embedding vector(384)
);

-- Topics (entity)
CREATE TABLE topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    mention_count INTEGER DEFAULT 0,
    first_mentioned_at TIMESTAMPTZ,
    last_mentioned_at TIMESTAMPTZ,
    embedding vector(384)
);

-- Relationships (junction tables for knowledge graph edges)
CREATE TABLE entity_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    source_type VARCHAR(20) NOT NULL,  -- person, project, decision, action_item, topic
    source_id UUID NOT NULL,
    target_type VARCHAR(20) NOT NULL,
    target_id UUID NOT NULL,
    relationship VARCHAR(50) NOT NULL,  -- owns, decided, assigned_to, related_to, mentions
    meeting_id UUID REFERENCES meetings(id),
    strength FLOAT DEFAULT 1.0,  -- accumulates with repeated mentions
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_type, source_id, target_type, target_id, relationship)
);

-- Contradictions detected
CREATE TABLE contradictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(id),
    decision_a_id UUID REFERENCES decisions(id),
    decision_b_id UUID REFERENCES decisions(id),
    description TEXT NOT NULL,
    severity VARCHAR(20) DEFAULT 'medium',  -- low, medium, high
    resolved BOOLEAN DEFAULT FALSE,
    detected_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Indexes

```sql
-- Vector similarity search
CREATE INDEX idx_transcript_embedding ON transcript_segments
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_decisions_embedding ON decisions
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
CREATE INDEX idx_action_items_embedding ON action_items
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- Temporal queries
CREATE INDEX idx_meetings_org_time ON meetings(org_id, started_at DESC);
CREATE INDEX idx_decisions_org_time ON decisions(org_id, decided_at DESC);
CREATE INDEX idx_action_items_status ON action_items(org_id, status, due_date);

-- Full-text search
CREATE INDEX idx_transcript_text ON transcript_segments
    USING gin(to_tsvector('english', text));

-- Knowledge graph traversal
CREATE INDEX idx_relationships_source ON entity_relationships(source_type, source_id);
CREATE INDEX idx_relationships_target ON entity_relationships(target_type, target_id);
```

---

## 4. Processing Pipeline

```
Meeting Audio → Recall.ai Bot
                    │
                    ▼
            Audio Stream (WebSocket)
                    │
                    ▼
        ┌───────────────────────┐
        │  faster-whisper       │  (GPU, ~10x real-time)
        │  Transcription        │
        │  Output: text + times │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  pyannote 3.x         │  (GPU)
        │  Speaker Diarization  │
        │  Output: who said what│
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  Speaker Matching     │  (match diarized speakers to known people)
        │  - Voice fingerprint  │
        │  - Name mention heur. │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  nomic-embed-text     │  (CPU, batch)
        │  Embed segments       │
        │  Output: 384-dim vecs │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  Claude API           │  (Sonnet)
        │  Entity Extraction    │
        │  - Decisions          │
        │  - Action items       │
        │  - Topics             │
        │  - People mentions    │
        │  - Relationships      │
        │  - Contradictions     │
        │  Output: structured   │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  Knowledge Graph      │
        │  Update               │
        │  - Upsert entities    │
        │  - Create edges       │
        │  - Update temporals   │
        │  - Detect patterns    │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │  Summary Generation   │  (Claude API)
        │  - Meeting summary    │
        │  - Key decisions      │
        │  - Action items list  │
        │  - Pre-meeting briefs │
        └───────────────────────┘
```

### Processing Times (estimated, 1-hour meeting)

| Step | Time | Cost |
|------|------|------|
| Transcription (faster-whisper, GPU) | ~6 min | Free (local) |
| Diarization (pyannote, GPU) | ~4 min | Free (local) |
| Embedding (nomic, CPU) | ~2 min | Free (local) |
| Entity extraction (Claude Sonnet) | ~1 min | ~$0.15 |
| Summary generation (Claude Sonnet) | ~30 sec | ~$0.05 |
| **Total** | **~14 min** | **~$0.20** |

With Recall.ai ($0.50/hr) + Deepgram ($0.75/hr for real-time alternative):
- **Total cost per 1-hr meeting:** $0.70 - $1.45

---

## 5. API Design

### Authentication

```
POST   /api/auth/register          # Email + password signup
POST   /api/auth/login             # Email + password login
POST   /api/auth/oauth/google      # Google OAuth callback
POST   /api/auth/refresh           # Refresh JWT
DELETE /api/auth/logout            # Invalidate session
```

### Meetings

```
GET    /api/meetings               # List meetings (paginated, filtered)
GET    /api/meetings/:id           # Meeting detail
GET    /api/meetings/:id/transcript  # Full transcript with speakers
GET    /api/meetings/:id/summary   # AI summary
GET    /api/meetings/:id/entities  # Extracted entities
POST   /api/meetings/:id/reprocess # Re-run processing pipeline
```

### Knowledge Graph

```
GET    /api/knowledge/search       # Semantic search across all entities
GET    /api/knowledge/people       # List people in org
GET    /api/knowledge/people/:id   # Person detail + meeting history
GET    /api/knowledge/projects     # List projects
GET    /api/knowledge/projects/:id # Project detail + related meetings
GET    /api/knowledge/decisions    # List decisions (filterable)
GET    /api/knowledge/action-items # List action items (status filter)
GET    /api/knowledge/topics       # List topics
GET    /api/knowledge/graph        # Graph visualization data
GET    /api/knowledge/contradictions # Detected contradictions
```

### @Kura Query

```
POST   /api/kura/ask               # Natural language query
  Body: { "question": "What did we decide about pricing?" }
  Response: {
    "answer": "...",
    "sources": [{ meeting_id, timestamp, excerpt }],
    "confidence": 0.92
  }

POST   /api/kura/brief             # Pre-meeting brief
  Body: { "meeting_id": "upcoming-meeting-uuid" }

GET    /api/kura/suggestions       # Proactive insights
```

### Calendar & Integrations

```
POST   /api/integrations/google/connect    # OAuth flow
POST   /api/integrations/outlook/connect   # OAuth flow
DELETE /api/integrations/:provider/disconnect
GET    /api/integrations/status            # Connection health

POST   /api/integrations/slack/install     # Slack app install
POST   /api/integrations/slack/events      # Slack event webhook
```

### Admin

```
GET    /api/admin/org               # Org settings
PUT    /api/admin/org               # Update org settings
GET    /api/admin/users             # User management
PUT    /api/admin/users/:id/role    # Change user role
GET    /api/admin/usage             # Usage stats (meetings, storage, API calls)
GET    /api/admin/audit             # Audit log
PUT    /api/admin/retention         # Data retention policy
```

---

## 6. Entity Extraction Prompt

Claude Sonnet receives transcript chunks (~5000 tokens) with this system prompt:

```
You are an entity extraction engine for meeting transcripts. Extract structured entities from the provided transcript segment.

Return a JSON object with:
{
  "decisions": [
    {"description": "...", "decided_by": "speaker name", "confidence": 0.0-1.0}
  ],
  "action_items": [
    {"description": "...", "assignee": "speaker name", "due_date": "YYYY-MM-DD or null"}
  ],
  "topics": [
    {"name": "...", "description": "..."}
  ],
  "people_mentioned": [
    {"name": "...", "role": "...", "context": "..."}
  ],
  "relationships": [
    {"source": "entity name", "target": "entity name", "type": "owns|decided|assigned_to|related_to|mentions"}
  ],
  "potential_contradictions": [
    {"statement": "...", "speaker": "...", "contradicts": "description of conflicting info"}
  ]
}

Rules:
- Only extract entities with clear evidence in the transcript
- Set confidence < 0.7 for ambiguous decisions
- Do not infer action items that weren't explicitly stated
- Flag potential contradictions with prior context provided
```

---

## 7. Query Engine

The @Kura query flow:

1. **Parse intent** — Classify query type (decision lookup, person info, project status, action items, general)
2. **Semantic search** — Embed query with nomic-embed, search pgvector across relevant tables
3. **Context assembly** — Gather top-k results + surrounding transcript context + related entities from knowledge graph
4. **Answer generation** — Claude Sonnet generates answer with source citations
5. **Confidence scoring** — Based on source relevance scores and answer coherence

```python
async def ask_kura(org_id: str, question: str) -> KuraAnswer:
    # 1. Embed the question
    query_vec = embed_model.encode(question)

    # 2. Search across entity types
    decisions = await search_decisions(org_id, query_vec, limit=5)
    segments = await search_transcript_segments(org_id, query_vec, limit=10)
    action_items = await search_action_items(org_id, query_vec, limit=5)

    # 3. Assemble context
    context = assemble_context(decisions, segments, action_items)

    # 4. Generate answer
    answer = await claude_generate_answer(question, context)

    # 5. Return with sources
    return KuraAnswer(
        answer=answer.text,
        sources=answer.sources,
        confidence=answer.confidence,
    )
```

---

## 8. Deployment

### Development (Docker Compose)

```yaml
version: '3.8'
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql://kura:kura@db:5432/kura
      - REDIS_URL=redis://redis:6379/0
      - CLAUDE_API_KEY=${CLAUDE_API_KEY}
      - RECALL_API_KEY=${RECALL_API_KEY}
    depends_on: [db, redis]

  worker:
    build: .
    command: celery -A kura.worker worker -l info -c 2
    environment:
      - DATABASE_URL=postgresql://kura:kura@db:5432/kura
      - REDIS_URL=redis://redis:6379/0
    depends_on: [db, redis]

  db:
    image: pgvector/pgvector:pg16
    volumes: ["pgdata:/var/lib/postgresql/data"]
    environment:
      - POSTGRES_USER=kura
      - POSTGRES_PASSWORD=kura
      - POSTGRES_DB=kura

  redis:
    image: redis:7-alpine
    volumes: ["redisdata:/data"]

  frontend:
    build: ./frontend
    ports: ["3000:3000"]

volumes:
  pgdata:
  redisdata:
```

### Production (Kubernetes)

- **API:** 2-4 replicas behind load balancer, autoscale on CPU
- **Workers:** 2-8 replicas, autoscale on queue depth
- **GPU Workers:** 1-2 replicas with GPU (transcription + diarization + embedding)
- **PostgreSQL:** Managed (AWS RDS, Supabase, or Neon) with pgvector extension
- **Redis:** Managed (ElastiCache or Upstash)
- **Storage:** S3/R2 for audio files
- **CDN:** Cloudflare for static assets

---

## 9. Cost Analysis Per User

### Pro User ($29/mo) — ~10 meetings/month, avg 45 min each

| Component | Cost/Meeting | Monthly |
|-----------|-------------|---------|
| Recall.ai bot | $0.38 | $3.75 |
| Transcription (local GPU) | $0.00 | $0.00 |
| Diarization (local GPU) | $0.00 | $0.00 |
| Embedding (local CPU) | $0.00 | $0.00 |
| Claude API (extraction + summary) | $0.20 | $2.00 |
| Claude API (@Kura queries, ~20/mo) | — | $1.00 |
| GPU compute (shared, amortized) | — | $2.00 |
| Database + storage | — | $0.50 |
| **Total** | | **$9.25** |
| **Gross margin** | | **68%** |

### Team User ($49/user/mo) — Higher volume, shared org context

| Component | Monthly per user |
|-----------|-----------------|
| Infrastructure (amortized) | $1.85 |
| Claude API | $4.00 |
| Recall.ai | $5.00 |
| Storage + DB | $1.00 |
| **Total** | **$11.85** |
| **Gross margin** | **76%** |

### At Scale (1000+ users)

- Bulk Recall.ai pricing: ~$0.35/hr
- GPU amortization drops significantly
- Per-user cost drops to ~$6-8/month
- **Gross margin: 78-92%**

---

## 10. MVP Scope (8-10 Weeks)

### Week 1-2: Foundation
- [ ] Project scaffolding (FastAPI + React + Docker Compose)
- [ ] PostgreSQL + pgvector schema + migrations (Alembic)
- [ ] User auth (email/password + Google OAuth)
- [ ] Basic React dashboard skeleton

### Week 3-4: Meeting Pipeline
- [ ] Google Calendar integration (OAuth + webhook for new events)
- [ ] Recall.ai bot integration (create bot, receive webhook on completion)
- [ ] Audio download + faster-whisper transcription
- [ ] pyannote speaker diarization
- [ ] Transcript storage with speaker attribution

### Week 5-6: Intelligence
- [ ] nomic-embed-text embedding pipeline
- [ ] Claude entity extraction (decisions, action items, topics, people)
- [ ] Knowledge graph storage (entities + relationships)
- [ ] Meeting summary generation
- [ ] Semantic search across transcripts + entities

### Week 7-8: User Experience
- [ ] Meeting list + detail view (transcript, summary, entities)
- [ ] @Kura query interface (ask questions, get answers with sources)
- [ ] Knowledge explorer (list view of people, projects, decisions)
- [ ] Action items tracker
- [ ] Basic pre-meeting brief

### Week 9-10: Polish + Launch
- [ ] Error handling + retry logic
- [ ] Usage tracking + billing hooks
- [ ] Onboarding flow
- [ ] Landing page
- [ ] Beta invite system
- [ ] Deploy to production (Fly.io or Railway)

### Out of Scope for MVP
- Slack/Teams integration (Stage 3)
- Voice participation (Stage 4)
- On-premise deployment
- Team/org features (shared memory)
- Advanced analytics
- Outlook calendar

---

## 11. Scalability Considerations

### Database
- **Partitioning:** Partition transcript_segments by org_id + month for large tenants
- **Read replicas:** Offload search queries to read replicas
- **pgvector scaling:** Switch from IVFFlat to HNSW index at >1M vectors. Consider dedicated vector DB (Qdrant, Pinecone) if pgvector becomes bottleneck

### Processing Pipeline
- **Queue-based:** All processing is async via Celery. Scale workers independently
- **GPU sharing:** Multiple tenants share GPU workers. Batch transcription jobs during off-peak
- **Streaming transcription:** For real-time use (Stage 4), switch to Deepgram streaming API

### Multi-tenancy
- **Data isolation:** All queries scoped by org_id. Row-level security in PostgreSQL
- **Rate limiting:** Per-org API rate limits. Per-user query limits
- **Resource quotas:** Meeting minutes/month per plan tier

### Caching
- **Redis:** Cache entity lookups, recent queries, meeting summaries
- **Embedding cache:** Cache frequently queried embeddings
- **CDN:** Static assets + pre-generated briefs

---

## 12. Security (Summary)

See [Security Architecture](security-architecture.md) for full details.

- **Encryption:** AES-256-GCM at rest, TLS 1.3 in transit, per-tenant DEKs
- **Auth:** JWT + refresh tokens, Google OAuth, SSO/SAML (Enterprise)
- **RBAC:** Admin, Member, Viewer roles per org
- **Consent:** Recording consent engine with per-meeting opt-in/out
- **Audit:** Full audit log of all data access
- **Compliance:** SOC 2 Type I (Month 6), GDPR-ready, HIPAA-eligible (Enterprise)
- **On-prem:** Air-gapped deployment option with local Whisper + local LLM
