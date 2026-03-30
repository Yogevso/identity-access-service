from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ValidationErrorItem(BaseModel):
    field: str
    message: str
    type: str
    input: Any | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ValidationErrorItem] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
