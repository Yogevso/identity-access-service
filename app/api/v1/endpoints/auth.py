from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.auth import (
    AuthTokensResponse,
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    RegisterRequest,
)
from app.services.auth import (
    AuthConflictError,
    AuthResult,
    AuthService,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


def build_auth_response(result: AuthResult) -> AuthTokensResponse:
    return AuthTokensResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        access_token_expires_in=result.access_token_expires_in,
        user=result.user,
        tenant=result.tenant,
    )


@router.post("/register", response_model=AuthTokensResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> AuthTokensResponse:
    service = AuthService(db, request.app.state.settings)

    try:
        result = service.register(
            payload,
            ip_address=request.client.host if request.client is not None else None,
            user_agent=request.headers.get("user-agent"),
        )
    except AuthConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return build_auth_response(result)


@router.post("/login", response_model=AuthTokensResponse, status_code=status.HTTP_200_OK)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> AuthTokensResponse:
    service = AuthService(db, request.app.state.settings)

    try:
        result = service.login(
            payload,
            ip_address=request.client.host if request.client is not None else None,
            user_agent=request.headers.get("user-agent"),
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return build_auth_response(result)


@router.post("/refresh", response_model=AuthTokensResponse, status_code=status.HTTP_200_OK)
def refresh(
    payload: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> AuthTokensResponse:
    service = AuthService(db, request.app.state.settings)

    try:
        result = service.refresh(
            payload.refresh_token,
            ip_address=request.client.host if request.client is not None else None,
            user_agent=request.headers.get("user-agent"),
        )
    except InvalidRefreshTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return build_auth_response(result)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: LogoutRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> Response:
    service = AuthService(db, request.app.state.settings)
    service.logout(
        payload.refresh_token,
        ip_address=request.client.host if request.client is not None else None,
        user_agent=request.headers.get("user-agent"),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
