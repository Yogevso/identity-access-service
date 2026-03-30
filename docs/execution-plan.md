# Engineering Execution Plan

## Delivery Strategy

The build will move in vertical slices, each leaving the repository in a runnable state. The target is not a throwaway demo but a maintainable backend foundation with clear upgrade paths.

## Architecture Decisions

### Application Style

- FastAPI for API and OpenAPI generation
- SQLAlchemy 2.x ORM for persistence
- Alembic for schema migrations
- PostgreSQL as the primary runtime database
- Docker Compose for local orchestration

### Backend Conventions

- Versioned API under `/api/v1`
- Application factory for testability
- Service layer for business logic
- Dependency injection for DB sessions and auth context
- Explicit models/schemas separation
- Environment-driven configuration via `pydantic-settings`

### Security Posture for v1

- JWT access tokens with explicit expiry
- Hashed refresh token persistence
- Role and tenant checks in service code
- Audit log coverage for security-relevant mutations

## Phased Plan

### Phase 1: Foundation

Deliverables:

- Repo skeleton
- Config module
- DB engine/session setup
- Domain models and initial migration
- Health endpoint
- Docker, Compose, CI, baseline test

Acceptance criteria:

- `docker compose up --build` brings up API and PostgreSQL
- `/api/v1/health` reports application and database status
- `alembic upgrade head` succeeds on a fresh database

### Phase 2: Auth Core

Deliverables:

- Password hashing utility
- Register endpoint
- Login endpoint
- Access and refresh token creation
- Refresh token rotation endpoint
- Logout endpoint

Acceptance criteria:

- Valid credentials return access and refresh tokens
- Invalid credentials return `401`
- Refresh flow invalidates old token on rotation

### Phase 3: RBAC

Deliverables:

- Auth dependency that resolves current principal
- Role guard dependency
- Protected example endpoints

Acceptance criteria:

- `USER` cannot reach admin routes
- `TENANT_ADMIN` cannot perform system-admin actions
- `SYS_ADMIN` can perform cross-tenant operations

### Phase 4: Tenant Isolation

Deliverables:

- Tenant CRUD
- Tenant-aware service/query helpers
- Isolation tests around cross-tenant access attempts

Acceptance criteria:

- Tenant admins see only users in their own tenant
- Cross-tenant resource access is rejected with `403` or `404` by design

### Phase 5: User Management

Deliverables:

- Create/list/delete users
- Role assignment/change flows
- Pagination and filters for listing

Acceptance criteria:

- Tenant admin can manage users inside their tenant
- Tenant admin cannot create `SYS_ADMIN`
- Role changes are audited

### Phase 6: Audit Logging

Deliverables:

- Audit logging service
- Integration points in auth and admin mutations
- Admin-facing audit listing endpoint

Acceptance criteria:

- Login and role-change events are queryable
- Audit records carry actor, tenant, resource, and timestamp

### Phase 7: Hardening

Deliverables:

- Error response consistency
- Expanded test coverage
- Operational docs and seed workflow
- Optional rate limiting and login-attempt controls

Acceptance criteria:

- CI enforces linting and tests
- Core business rules are covered by automated tests
- Docs describe setup, env vars, and architecture clearly

## Work Breakdown

### Foundation Tasks

1. Create dependency manifest and package layout.
2. Add configuration, logging, DB engine, and session factory.
3. Model tenant, user, refresh token, and audit log entities.
4. Wire Alembic and ship initial migration.
5. Expose health route and root metadata route.
6. Add Dockerfile, Compose stack, `.env.example`, and CI.
7. Add health endpoint test with an isolated test DB.

### Auth Tasks

1. Define request/response schemas.
2. Implement password hashing and token utilities.
3. Add auth service with register/login/refresh/logout flows.
4. Persist and revoke refresh tokens correctly.
5. Emit audit events on login and logout.

### RBAC and Tenancy Tasks

1. Add principal model from JWT claims.
2. Add role guard dependencies.
3. Introduce tenant-scoped query helpers and service assertions.
4. Add cross-tenant authorization tests.

## Definition of Done

A phase is complete only when:

- Code is committed in a coherent runnable state
- API behavior is documented
- Tests exist for the new behavior
- Linting passes
- Security and tenant-boundary implications are considered explicitly

## Testing Strategy

- Unit tests for utilities and pure business logic
- Integration tests for API routes and DB persistence
- Negative-path tests for auth and permission failures
- Isolation tests for cross-tenant access attempts
- Migration smoke test in CI

## Risks and Mitigations

- Risk: auth work can sprawl into framework glue.
  Mitigation: keep token, hashing, and auth service responsibilities separated.

- Risk: tenant leakage through ad hoc queries.
  Mitigation: centralize tenant scoping in service methods and verify with tests.

- Risk: overcomplicating v1 with fine-grained permissions too early.
  Mitigation: lock v1 to RBAC and add policy granularity only after the core flows stabilize.
