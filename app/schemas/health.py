from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthComponent(BaseModel):
    status: Literal["ok", "degraded"]
    latency_ms: int = Field(ge=0)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    environment: str
    version: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    database: HealthComponent
