from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class Status(str, Enum):
    FOUND = "FOUND"
    NOT_FOUND = "NOT_FOUND"
    ERROR = "ERROR"


class Finding(BaseModel):
    entity: str
    entity_type: str
    source: str
    status: Status
    url: str | None = None
    evidence: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
