from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.errors import ErrorBody, ErrorResponse, ValidationErrorItem

STATUS_CODE_MAP = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "validation_error",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_error",
}


def build_error_response(
    *,
    status_code: int,
    message: str,
    code: str | None = None,
    details: list[ValidationErrorItem] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=code or STATUS_CODE_MAP.get(status_code, "http_error"),
            message=message,
            details=details,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        return build_error_response(
            status_code=exc.status_code,
            message=_stringify_detail(exc.detail),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return build_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="Request validation failed.",
            details=[
                ValidationErrorItem(
                    field=".".join(str(part) for part in error["loc"]),
                    message=error["msg"],
                    type=error["type"],
                    input=error.get("input"),
                )
                for error in exc.errors()
            ],
        )


def _stringify_detail(detail: object) -> str:
    if isinstance(detail, str):
        return detail
    return "Request could not be processed."
