from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    parse_refresh_token,
    verify_password,
    verify_refresh_token_secret,
)
from app.models.enums import AuditAction, Role
from app.models.refresh_token import RefreshToken
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.audit import record_audit_event


class AuthConflictError(Exception):
    """Raised when a unique auth-side resource already exists."""


class InvalidCredentialsError(Exception):
    """Raised when login credentials are invalid."""


class InvalidRefreshTokenError(Exception):
    """Raised when a refresh token is invalid or expired."""


@dataclass(slots=True)
class AuthResult:
    user: User
    tenant: Tenant
    access_token: str
    refresh_token: str
    access_token_expires_in: int


class AuthService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings

    def register(
        self,
        payload: RegisterRequest,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthResult:
        tenant_exists = self.db.scalar(select(Tenant).where(Tenant.slug == payload.tenant_slug))
        if tenant_exists is not None:
            raise AuthConflictError("Tenant slug already exists.")

        tenant = Tenant(
            name=payload.tenant_name,
            slug=payload.tenant_slug,
        )
        user = User(
            tenant=tenant,
            email=str(payload.email),
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
            role=Role.TENANT_ADMIN,
        )
        self.db.add_all([tenant, user])
        self.db.flush()

        auth_result = self._issue_tokens_for_user(user)
        record_audit_event(
            self.db,
            action=AuditAction.TENANT_CREATED,
            resource_type="tenant",
            resource_id=str(tenant.id),
            tenant_id=tenant.id,
            actor_user_id=user.id,
            details={"tenant_slug": tenant.slug, "source": "self_signup"},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        record_audit_event(
            self.db,
            action=AuditAction.USER_CREATED,
            resource_type="user",
            resource_id=str(user.id),
            tenant_id=tenant.id,
            actor_user_id=user.id,
            details={"role": user.role.value, "source": "self_signup"},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.commit()
        return auth_result

    def login(
        self,
        payload: LoginRequest,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthResult:
        tenant = self.db.scalar(select(Tenant).where(Tenant.slug == payload.tenant_slug))
        if tenant is None or not tenant.is_active:
            self._record_login_failure(
                tenant_id=tenant.id if tenant is not None else None,
                email=str(payload.email),
                tenant_slug=payload.tenant_slug,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise InvalidCredentialsError("Invalid tenant, email, or password.")

        user = self.db.scalar(
            select(User)
            .options(joinedload(User.tenant))
            .where(User.tenant_id == tenant.id, User.email == str(payload.email))
        )
        if (
            user is None
            or not user.is_active
            or not verify_password(payload.password, user.password_hash)
        ):
            self._record_login_failure(
                tenant_id=tenant.id,
                email=str(payload.email),
                tenant_slug=tenant.slug,
                actor_user_id=user.id if user is not None else None,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise InvalidCredentialsError("Invalid tenant, email, or password.")

        user.last_login_at = datetime.now(UTC)
        auth_result = self._issue_tokens_for_user(user)
        record_audit_event(
            self.db,
            action=AuditAction.LOGIN_SUCCESS,
            resource_type="user",
            resource_id=str(user.id),
            tenant_id=user.tenant_id,
            actor_user_id=user.id,
            details={"tenant_slug": user.tenant.slug},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.commit()
        return auth_result

    def refresh(
        self,
        refresh_token: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthResult:
        stored_token = self._get_valid_refresh_token(refresh_token)
        stored_token.revoked_at = datetime.now(UTC)
        stored_token.last_used_at = datetime.now(UTC)

        auth_result = self._issue_tokens_for_user(stored_token.user)
        record_audit_event(
            self.db,
            action=AuditAction.TOKEN_REVOKED,
            resource_type="refresh_token",
            resource_id=str(stored_token.id),
            tenant_id=stored_token.user.tenant_id,
            actor_user_id=stored_token.user_id,
            details={"reason": "rotation"},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.commit()
        return auth_result

    def logout(
        self,
        refresh_token: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        try:
            token_id, secret = parse_refresh_token(refresh_token)
        except (ValueError, TypeError):
            return

        stored_token = self.db.scalar(
            select(RefreshToken)
            .options(joinedload(RefreshToken.user))
            .where(RefreshToken.id == token_id)
        )
        if stored_token is None:
            return

        if not verify_refresh_token_secret(secret, stored_token.token_hash):
            return

        if stored_token.revoked_at is not None:
            return

        stored_token.revoked_at = datetime.now(UTC)
        stored_token.last_used_at = datetime.now(UTC)
        record_audit_event(
            self.db,
            action=AuditAction.TOKEN_REVOKED,
            resource_type="refresh_token",
            resource_id=str(stored_token.id),
            tenant_id=stored_token.user.tenant_id,
            actor_user_id=stored_token.user_id,
            details={"reason": "logout"},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.commit()

    def _issue_tokens_for_user(self, user: User) -> AuthResult:
        refresh_bundle = create_refresh_token(settings=self.settings)
        access_token = create_access_token(user=user, settings=self.settings)
        refresh_token = RefreshToken(
            id=refresh_bundle.token_id,
            user=user,
            token_hash=refresh_bundle.token_hash,
            expires_at=refresh_bundle.expires_at,
        )
        self.db.add(refresh_token)
        self.db.flush()

        return AuthResult(
            user=user,
            tenant=user.tenant,
            access_token=access_token,
            refresh_token=refresh_bundle.plain_token,
            access_token_expires_in=self.settings.access_token_ttl_minutes * 60,
        )

    def _get_valid_refresh_token(self, refresh_token: str) -> RefreshToken:
        try:
            token_id, secret = parse_refresh_token(refresh_token)
        except (ValueError, TypeError) as exc:
            raise InvalidRefreshTokenError("Refresh token is invalid.") from exc

        stored_token = self.db.scalar(
            select(RefreshToken)
            .options(joinedload(RefreshToken.user).joinedload(User.tenant))
            .where(RefreshToken.id == token_id)
        )
        if stored_token is None:
            raise InvalidRefreshTokenError("Refresh token is invalid.")

        if not verify_refresh_token_secret(secret, stored_token.token_hash):
            raise InvalidRefreshTokenError("Refresh token is invalid.")

        if stored_token.revoked_at is not None or self._is_expired(stored_token.expires_at):
            raise InvalidRefreshTokenError("Refresh token is invalid.")

        if not stored_token.user.is_active or not stored_token.user.tenant.is_active:
            raise InvalidRefreshTokenError("Refresh token is invalid.")

        return stored_token

    def _record_login_failure(
        self,
        *,
        email: str,
        tenant_slug: str,
        tenant_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        record_audit_event(
            self.db,
            action=AuditAction.LOGIN_FAILURE,
            resource_type="auth",
            resource_id="login",
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            details={"email": email, "tenant_slug": tenant_slug},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.commit()

    @staticmethod
    def _is_expired(expires_at: datetime) -> bool:
        normalized_expires_at = expires_at
        if normalized_expires_at.tzinfo is None:
            normalized_expires_at = normalized_expires_at.replace(tzinfo=UTC)

        return normalized_expires_at <= datetime.now(UTC)
