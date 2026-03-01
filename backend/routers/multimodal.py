from fastapi import APIRouter, Depends, File, Form, UploadFile

from dependencies.auth import require_approved_doctor_or_admin
from models.multimodal_models import MultimodalResponse
from services.multimodal_service import run_multimodal_pipeline

router = APIRouter(prefix="/api/v1/multimodal", tags=["Multimodal"])


@router.post("/analyze", response_model=MultimodalResponse)
async def analyze_multimodal(
    file: UploadFile | None = File(default=None),
    symptoms: str | None = Form(default=None),
    _: dict = Depends(require_approved_doctor_or_admin),
) -> dict:
    image_bytes = None
    if file is not None:
        image_bytes = await file.read()

    return await run_multimodal_pipeline(image_bytes=image_bytes, symptoms=symptoms)
