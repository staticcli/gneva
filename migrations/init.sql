-- Gneva: Initial database schema
-- PostgreSQL 16
-- Note: pgvector extension added when available (Linux/Docker deployment)
-- On Windows dev, embedding columns use JSONB fallback

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Try to create pgvector if available, ignore error if not
DO $$ BEGIN
    CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pgvector not available — using JSONB for embeddings';
END $$;

-- Organizations and Users
CREATE TABLE organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    slug        TEXT UNIQUE NOT NULL,
    plan        TEXT NOT NULL DEFAULT 'starter',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    email           TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'member',
    speaker_profile JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Meetings
CREATE TABLE meetings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    recall_bot_id   TEXT,
    platform        TEXT NOT NULL,
    title           TEXT,
    scheduled_at    TIMESTAMPTZ,
    started_at      TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    duration_sec    INTEGER,
    participant_count INTEGER,
    status          TEXT NOT NULL DEFAULT 'scheduled',
    raw_audio_path  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_meetings_org_id ON meetings(org_id);
CREATE INDEX idx_meetings_started_at ON meetings(started_at DESC);

-- Transcripts
CREATE TABLE transcripts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id  UUID NOT NULL REFERENCES meetings(id),
    version     INTEGER NOT NULL DEFAULT 1,
    full_text   TEXT NOT NULL,
    word_count  INTEGER,
    language    TEXT DEFAULT 'en',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(meeting_id, version)
);

CREATE TABLE transcript_segments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transcript_id   UUID NOT NULL REFERENCES transcripts(id),
    speaker_id      UUID REFERENCES users(id),
    speaker_label   TEXT,
    start_ms        INTEGER NOT NULL,
    end_ms          INTEGER NOT NULL,
    text            TEXT NOT NULL,
    confidence      FLOAT,
    embedding       JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_segments_transcript ON transcript_segments(transcript_id);

-- Knowledge Graph: Entities
CREATE TABLE entities (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES organizations(id),
    type        TEXT NOT NULL,
    name        TEXT NOT NULL,
    canonical   TEXT NOT NULL,
    description TEXT,
    metadata_json JSONB DEFAULT '{}',
    embedding   JSONB,
    first_seen  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
    mention_count INTEGER NOT NULL DEFAULT 1,
    UNIQUE(org_id, type, canonical)
);

CREATE INDEX idx_entities_org_type ON entities(org_id, type);
CREATE INDEX idx_entities_canonical ON entities(org_id, canonical text_pattern_ops);

-- Knowledge Graph: Relationships
CREATE TABLE entity_relationships (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    source_id       UUID NOT NULL REFERENCES entities(id),
    target_id       UUID NOT NULL REFERENCES entities(id),
    relationship    TEXT NOT NULL,
    confidence      FLOAT NOT NULL DEFAULT 1.0,
    evidence        TEXT,
    meeting_id      UUID REFERENCES meetings(id),
    valid_from      TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_until     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_relationships_source ON entity_relationships(source_id);
CREATE INDEX idx_relationships_target ON entity_relationships(target_id);
CREATE INDEX idx_relationships_org ON entity_relationships(org_id, relationship);

-- Entity mentions per meeting
CREATE TABLE entity_mentions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID NOT NULL REFERENCES entities(id),
    meeting_id      UUID NOT NULL REFERENCES meetings(id),
    segment_id      UUID REFERENCES transcript_segments(id),
    context         TEXT,
    mention_type    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mentions_entity ON entity_mentions(entity_id);
CREATE INDEX idx_mentions_meeting ON entity_mentions(meeting_id);

-- Decisions
CREATE TABLE decisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID NOT NULL REFERENCES entities(id),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    meeting_id      UUID NOT NULL REFERENCES meetings(id),
    statement       TEXT NOT NULL,
    rationale       TEXT,
    owner_id        UUID REFERENCES users(id),
    status          TEXT NOT NULL DEFAULT 'active',
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
    priority        TEXT DEFAULT 'medium',
    status          TEXT NOT NULL DEFAULT 'open',
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
    action_items_json TEXT NOT NULL DEFAULT '[]',
    topics_covered  TEXT[] NOT NULL DEFAULT '{}',
    sentiment       TEXT,
    follow_up_needed BOOLEAN DEFAULT false,
    embedding       JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Contradiction Log
CREATE TABLE contradictions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    entity_id_a     UUID NOT NULL REFERENCES entities(id),
    entity_id_b     UUID NOT NULL REFERENCES entities(id),
    description     TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'low',
    status          TEXT NOT NULL DEFAULT 'open',
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);

-- Gneva message log
CREATE TABLE gneva_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    meeting_id      UUID REFERENCES meetings(id),
    channel         TEXT NOT NULL,
    channel_ref     TEXT,
    direction       TEXT NOT NULL,
    content         TEXT NOT NULL,
    metadata_json   JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
