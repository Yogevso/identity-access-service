from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.principal import CurrentPrincipal
from app.core.security import InvalidAccessTokenError, decode_access_token
from app.db.session import get_db_session
from app.models.enums import Role
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db_session),
) -> CurrentPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized_error()

    try:
        claims = decode_access_token(credentials.credentials, settings=request.app.state.settings)
    except InvalidAccessTokenError as exc:
        raise _unauthorized_error() from exc

    user = db.scalar(
        select(User)
        .options(joinedload(User.tenant))
        .where(User.id == claims.user_id)
    )
    if user is None or not user.is_active or not user.tenant.is_active:
        raise _unauthorized_error()

    if user.tenant_id != claims.tenant_id or user.role != claims.role:
        raise _unauthorized_error()

    return CurrentPrincipal(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        email=user.email,
        full_name=user.full_name,
        tenant_slug=user.tenant.slug,
        tenant_name=user.tenant.name,
    )


def require_roles(*allowed_roles: Role) -> Callable[[CurrentPrincipal], CurrentPrincipal]:
    allowed = set(allowed_roles)

    def dependency(
        principal: CurrentPrincipal = Depends(get_current_principal),
    ) -> CurrentPrincipal:
        if principal.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return principal

    return dependency


def _unauthorized_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials were not provided or are invalid.",
        headers={"WWW-Authenticate": "Bearer"},
    )
