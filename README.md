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
- Login-attempt protection with temporary account lockout for repeated failures
- JWT-backed principal resolution and RBAC-protected example routes
- Tenant CRUD and tenant-scoped user listing with isolation checks
- Tenant-admin and system-admin user management with role changes and deactivation
- Queryable audit log APIs for tenant and system administrators
- Consistent JSON error envelope for validation, auth, permission, conflict, and not-found cases
- Dockerfile, Docker Compose, and CI workflow
- Integration tests for health, auth, RBAC, tenancy, user-management, and audit flows

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

Key auth and admin endpoints:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/admin/tenant/summary`
- `GET /api/v1/admin/system/summary`
- `GET /api/v1/tenants/me`
- `GET /api/v1/tenants/{tenant_id}`
- `GET /api/v1/tenants/{tenant_id}/users`
- `GET /api/v1/tenants`
- `POST /api/v1/tenants`
- `PATCH /api/v1/tenants/{tenant_id}`
- `POST /api/v1/tenants/{tenant_id}/users`
- `PATCH /api/v1/tenants/{tenant_id}/users/{user_id}/role`
- `DELETE /api/v1/tenants/{tenant_id}/users/{user_id}`
- `GET /api/v1/audit-logs`
- `GET /api/v1/tenants/{tenant_id}/audit-logs`

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
alembic upgrade head
```

## Error Model

Non-success responses use a consistent envelope:

```json
{
  "error": {
    "code": "forbidden",
    "message": "You do not have permission to perform this action.",
    "details": null
  }
}
```

Validation failures use `code: "validation_error"` and populate `details` with field-level items.

## Auth Hardening

- Access tokens are short-lived JWTs; refresh tokens are opaque, hashed at rest, rotated on refresh, and revocable on logout or user deactivation.
- Repeated failed login attempts against a valid active account trigger a temporary account lockout.
- The login endpoint keeps returning the same `401` error for invalid credentials, inactive accounts, and active lockouts to reduce account-enumeration leakage.

Relevant settings in `.env`:

- `MAX_FAILED_LOGIN_ATTEMPTS`
- `LOGIN_LOCKOUT_MINUTES`

## Project Layout

```text
identity-access-service/
|-- alembic/
|-- app/
|   |-- api/
|   |-- core/
|   |-- db/
|   |-- models/
|   |-- schemas/
|   |-- services/
|   `-- main.py
|-- docs/
|-- tests/
|-- .github/workflows/
|-- docker-compose.yml
|-- Dockerfile
`-- pyproject.toml
```

## Immediate Next Slices

- Broader test coverage for auth and tenancy boundaries
- Seed/bootstrap workflow for local admin setup
- Optional request-level rate limiting or abuse controls
