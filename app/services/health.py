from __future__ import annotations

from time import perf_counter

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.schemas.health import HealthComponent, HealthResponse


def build_health_response(db: Session, settings: Settings) -> HealthResponse:
    started_at = perf_counter()
    database_status = "ok"

    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        database_status = "degraded"

    latency_ms = int((perf_counter() - started_at) * 1000)
    overall_status = "ok" if database_status == "ok" else "degraded"

    return HealthResponse(
        status=overall_status,
        service=settings.app_name,
        environment=settings.app_env,
        version=settings.app_version,
        database=HealthComponent(status=database_status, latency_ms=latency_ms),
    )
