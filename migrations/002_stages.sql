-- Gneva: Stage 1 & 2 tables
-- Calendar events, consent logs, notifications, meeting patterns, follow-ups, speaker analytics

-- Calendar Events (synced from Google/Outlook)
CREATE TABLE calendar_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL REFERENCES organizations(id),
    user_id             UUID NOT NULL REFERENCES users(id),
    provider            TEXT NOT NULL,  -- google, outlook, icalendar
    provider_event_id   TEXT NOT NULL,
    title               TEXT NOT NULL,
    description         TEXT,
    meeting_url         TEXT,
    platform            TEXT,  -- zoom, meet, teams
    start_time          TIMESTAMPTZ NOT NULL,
    end_time            TIMESTAMPTZ NOT NULL,
    attendees_json      JSONB DEFAULT '[]'::jsonb,
    auto_join           BOOLEAN NOT NULL DEFAULT false,
    meeting_id          UUID REFERENCES meetings(id),
    synced_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_calendar_events_org ON calendar_events(org_id);
CREATE INDEX idx_calendar_events_user ON calendar_events(user_id);
CREATE INDEX idx_calendar_events_start ON calendar_events(start_time);
CREATE UNIQUE INDEX idx_calendar_events_provider_id ON calendar_events(org_id, provider, provider_event_id);

-- Consent Logs (recording/transcription consent per meeting)
CREATE TABLE consent_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    meeting_id      UUID NOT NULL REFERENCES meetings(id),
    consent_type    TEXT NOT NULL,  -- recording, transcription, ai_analysis
    method          TEXT NOT NULL,  -- chat_message, verbal, pre_meeting
    acknowledged_by TEXT,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata_json   JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_consent_logs_meeting ON consent_logs(meeting_id);
CREATE INDEX idx_consent_logs_org ON consent_logs(org_id);

-- Notifications
CREATE TABLE notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    type            TEXT NOT NULL,  -- meeting_complete, action_item_due, contradiction_detected, weekly_digest, follow_up_reminder
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    meeting_id      UUID REFERENCES meetings(id),
    action_item_id  UUID REFERENCES action_items(id),
    channel         TEXT NOT NULL DEFAULT 'in_app',  -- in_app, email, slack
    read            BOOLEAN NOT NULL DEFAULT false,
    sent_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notifications_user ON notifications(user_id, read);
CREATE INDEX idx_notifications_org ON notifications(org_id);
CREATE INDEX idx_notifications_created ON notifications(created_at DESC);

-- Meeting Patterns (detected cross-meeting insights)
CREATE TABLE meeting_patterns (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    pattern_type    TEXT NOT NULL,  -- recurring_topic, repeated_blocker, sentiment_trend, participation_gap, decision_reversal
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    confidence      FLOAT NOT NULL,
    evidence_json   JSONB DEFAULT '[]'::jsonb,
    severity        TEXT NOT NULL DEFAULT 'info',  -- info, warning, critical
    status          TEXT NOT NULL DEFAULT 'active',  -- active, dismissed, resolved
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    dismissed_at    TIMESTAMPTZ
);

CREATE INDEX idx_patterns_org_status ON meeting_patterns(org_id, status);
CREATE INDEX idx_patterns_type ON meeting_patterns(org_id, pattern_type);

-- Follow-Ups (action item reminders and decision checks)
CREATE TABLE follow_ups (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id),
    action_item_id  UUID REFERENCES action_items(id),
    meeting_id      UUID REFERENCES meetings(id),
    assigned_to     UUID REFERENCES users(id),
    type            TEXT NOT NULL,  -- action_reminder, decision_check, meeting_schedule
    description     TEXT NOT NULL,
    due_date        DATE NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending, sent, completed, skipped
    reminder_count  INTEGER NOT NULL DEFAULT 0,
    last_reminded_at TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_follow_ups_org ON follow_ups(org_id, status);
CREATE INDEX idx_follow_ups_assigned ON follow_ups(assigned_to, status);
CREATE INDEX idx_follow_ups_due ON follow_ups(due_date) WHERE status = 'pending';

-- Speaker Analytics (per-speaker per-meeting stats)
CREATE TABLE speaker_analytics (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID NOT NULL REFERENCES organizations(id),
    meeting_id          UUID NOT NULL REFERENCES meetings(id),
    speaker_label       TEXT NOT NULL,
    user_id             UUID REFERENCES users(id),
    talk_time_sec       FLOAT NOT NULL,
    word_count          INTEGER NOT NULL,
    interruption_count  INTEGER NOT NULL DEFAULT 0,
    question_count      INTEGER NOT NULL DEFAULT 0,
    sentiment_avg       FLOAT,
    topics_json         JSONB DEFAULT '[]'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_speaker_analytics_meeting ON speaker_analytics(meeting_id);
CREATE INDEX idx_speaker_analytics_org ON speaker_analytics(org_id);
CREATE INDEX idx_speaker_analytics_user ON speaker_analytics(user_id) WHERE user_id IS NOT NULL;
