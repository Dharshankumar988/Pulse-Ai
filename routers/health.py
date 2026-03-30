from fastapi import APIRouter

from services.health_service import get_health_status

router = APIRouter(prefix="/api/v1", tags=["Health"])


@router.get("/health")
def health_check() -> dict:
    return get_health_status()
