from fastapi import APIRouter

from .admin import router as admin_router
from .auth import router as auth_router
from .health import router as health_router
from .medical import router as medical_router
from .ml import router as ml_router
from .multimodal import router as multimodal_router
from .patient_management import router as patient_management_router
from .supabase import router as supabase_router

api_router = APIRouter()
api_router.include_router(admin_router)
api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(medical_router)
api_router.include_router(ml_router)
api_router.include_router(multimodal_router)
api_router.include_router(patient_management_router)
api_router.include_router(supabase_router)
