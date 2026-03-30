from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import Settings
from app.models.user import User


@dataclass(slots=True)
class RefreshTokenBundle:
    token_id: uuid.UUID
    plain_token: str
    token_hash: str
    expires_at: datetime


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(*, user: User, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user.id),
        "tenant_id": str(user.tenant_id),
        "role": user.role.value,
        "email": user.email,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
        "iss": settings.jwt_issuer,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(*, settings: Settings) -> RefreshTokenBundle:
    token_id = uuid.uuid4()
    secret = secrets.token_urlsafe(48)
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days)
    plain_token = f"{token_id}.{secret}"

    return RefreshTokenBundle(
        token_id=token_id,
        plain_token=plain_token,
        token_hash=hash_refresh_token_secret(secret),
        expires_at=expires_at,
    )


def parse_refresh_token(refresh_token: str) -> tuple[uuid.UUID, str]:
    token_id, secret = refresh_token.split(".", maxsplit=1)
    return uuid.UUID(token_id), secret


def hash_refresh_token_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def verify_refresh_token_secret(secret: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_refresh_token_secret(secret), expected_hash)
