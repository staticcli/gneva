"""Create performance indexes for common query patterns."""

from sqlalchemy import text


async def add_indexes(engine):
    """Create indexes if they do not already exist."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_meeting_org_id ON meetings(org_id)",
        "CREATE INDEX IF NOT EXISTS idx_meeting_status ON meetings(status)",
        "CREATE INDEX IF NOT EXISTS idx_entity_org_type ON entities(org_id, type)",
        "CREATE INDEX IF NOT EXISTS idx_entity_last_seen ON entities(last_seen)",
        "CREATE INDEX IF NOT EXISTS idx_decision_org_status ON decisions(org_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_action_item_org_status ON action_items(org_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_gneva_message_org_channel ON gneva_messages(org_id, channel)",
        "CREATE INDEX IF NOT EXISTS idx_transcript_meeting ON transcripts(meeting_id)",
    ]
    async with engine.begin() as conn:
        for stmt in indexes:
            await conn.execute(text(stmt))
