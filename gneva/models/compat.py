"""Cross-dialect type compatibility for PostgreSQL and SQLite."""

import uuid

from sqlalchemy import String, TypeDecorator, text as sa_text
from sqlalchemy.types import JSON

# Re-export JSON as our standard JSON type (works on both PG and SQLite)
# Use this instead of JSONB
CompatJSON = JSON


class CompatUUID(TypeDecorator):
    """UUID type that works on both PostgreSQL (native UUID) and SQLite (CHAR(36))."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(value)
        return value

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))


def compat_server_default(pg_default: str, sqlite_default: str | None = None):
    """Return a server_default that works on both dialects.

    For SQLite, we skip PostgreSQL-specific defaults like gen_random_uuid() and ::jsonb casts.
    """
    # This is called at module load time when we don't have dialect info.
    # We'll handle this differently — return None for SQLite-incompatible defaults
    # and generate UUIDs in Python instead.
    return None


# For UUID primary keys, generate in Python instead of relying on server_default
def new_uuid() -> uuid.UUID:
    return uuid.uuid4()
