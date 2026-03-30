from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.models.enums import Role


@dataclass(slots=True)
class CurrentPrincipal:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: Role
    email: str
    full_name: str
    tenant_slug: str
    tenant_name: str
