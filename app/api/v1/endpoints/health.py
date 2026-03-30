from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.health import HealthResponse
from app.services.health import build_health_response

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
def health_check(request: Request, db: Session = Depends(get_db_session)) -> HealthResponse:
    return build_health_response(db, request.app.state.settings)
