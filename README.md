# Identity Access Service

Production-style Identity and Access Management (IAM) backend built with FastAPI, PostgreSQL, SQLAlchemy, Alembic, Docker Compose, and GitHub Actions.

## Current Scope

This repository now includes the foundation layer for the service:

- FastAPI application factory with versioned routing
- Database configuration and SQLAlchemy session management
- Core domain models for tenants, users, refresh tokens, and audit logs
- Alembic migration scaffolding with an initial schema
- `/api/v1/health` endpoint with database connectivity check
- Auth endpoints for tenant signup, login, refresh rotation, and logout
- JWT-backed principal resolution and RBAC-protected example routes
- Dockerfile, Docker Compose, and CI workflow
- Integration tests for health, auth, and RBAC flows

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

Key auth endpoints:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/admin/tenant/summary`
- `GET /api/v1/admin/system/summary`

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

- Tenant-admin user management endpoints
- Audit trail emission for sensitive actions
- Broader test coverage for auth and tenancy boundaries
