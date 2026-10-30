import uuid
from sqlalchemy import TypeDecorator, String
from sqlalchemy.dialects.postgresql import UUID

class SafeUUIDType(TypeDecorator):
    """
    Coerces string UUIDs to Python uuid.UUID objects when binding,
    and returns uuid.UUID objects from database results.
    Supports PostgreSQL native UUID and SQLite String(36).
    """
    impl = UUID(as_uuid=True)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(String(36))
        return dialect.type_descriptor(UUID(as_uuid=True))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value) if dialect.name == "sqlite" else value
        if isinstance(value, str):
            try:
                u = uuid.UUID(value)
                return str(u) if dialect.name == "sqlite" else u
            except (ValueError, AttributeError):
                return value if dialect.name == "sqlite" else None
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (ValueError, AttributeError):
            return None

print("SafeUUIDType defined successfully.")

