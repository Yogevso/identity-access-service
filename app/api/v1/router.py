from fastapi import APIRouter

from app.api.v1.endpoints.audit import router as audit_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.rbac import router as rbac_router
from app.api.v1.endpoints.tenants import router as tenants_router
from app.api.v1.endpoints.users import router as users_router

router = APIRouter()
router.include_router(audit_router)
router.include_router(auth_router)
router.include_router(health_router)
router.include_router(rbac_router)
router.include_router(tenants_router)
router.include_router(users_router)
