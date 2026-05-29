"""ID generation utilities."""

import uuid

from ulid import ULID


def generate_id() -> str:
    return str(ULID())


def generate_uuid() -> uuid.UUID:
    return uuid.uuid4()


def generate_request_id() -> str:
    return f"req_{ULID()}"
