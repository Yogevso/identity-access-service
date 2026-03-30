# Identity Access Service

Production-style Identity and Access Management (IAM) backend built with FastAPI, PostgreSQL, SQLAlchemy, Alembic, Docker Compose, and GitHub Actions.

## Current Scope

This repository now includes the foundation layer for the service:

- FastAPI application factory with versioned routing
- Database configuration and SQLAlchemy session management
- Core domain models for tenants, users, refresh tokens, and audit logs
- Alembic migration scaffolding with an initial schema
- `/api/v1/health` endpoint with database connectivity check
- Dockerfile, Docker Compose, and CI workflow
- Baseline automated test for health/system readiness

The detailed product specification and phased execution plan live in:

- [docs/prd.md](docs/prd.md)
- [docs/execution-plan.md](docs/execution-plan.md)

## Quick Start

1. Copy `.env.example` to `.env`.
2. Start the stack:

```bash
docker compose up --build
```

3. Open:

- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/v1/health`

## Local Development

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install .[dev]
```

Run the API:

```bash
uvicorn app.main:app --reload
```

Run checks:

```bash
ruff check .
pytest
```

## Project Layout

```text
identity-access-service/
├── alembic/
├── app/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   └── main.py
├── docs/
├── tests/
├── .github/workflows/
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

## Immediate Next Slices

- Auth flows: register, login, refresh, logout
- RBAC enforcement dependencies and protected routes
- Tenant-admin user management endpoints
- Audit trail emission for sensitive actions
- Broader test coverage for auth and tenancy boundaries
