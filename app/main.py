from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import build_engine, build_session_factory


def create_application(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    configure_logging()

    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        description="Multi-tenant IAM backend for authentication and authorization workloads.",
        openapi_url=f"{app_settings.api_v1_prefix}/openapi.json",
        lifespan=build_lifespan(),
    )
    app.state.settings = app_settings
    app.state.engine = build_engine(app_settings.database_url)
    app.state.session_factory = build_session_factory(app.state.engine)
    register_exception_handlers(app)

    if app_settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"service": app_settings.app_name, "docs_url": "/docs"}

    app.include_router(api_router, prefix=app_settings.api_v1_prefix)
    return app


def build_lifespan():
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.engine.dispose()

    return lifespan


app = create_application()
