"""Immutable object delivery data, independent of the request's ORM session."""
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class FileDelivery:
    id: UUID
    bucket: str
    object_key: str
    name: str
    content_type: str
    size_bytes: int
    checksum: str

    @classmethod
    def capture(cls, record):
        return cls(**{name: getattr(record, name) for name in cls.__dataclass_fields__})
