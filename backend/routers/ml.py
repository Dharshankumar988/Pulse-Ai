from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from dependencies.auth import require_approved_doctor_or_admin
from models.ml_models import MLInferenceResponse, MLTask
from services.ml_service import (
    MLServiceError,
    build_error_response,
    get_model_load_status,
    run_ml_inference,
)

router = APIRouter(prefix="/api/v1/ml", tags=["ML"])


@router.get("/models/status")
def model_status(_: dict = Depends(require_approved_doctor_or_admin)) -> dict:
    return {"models": get_model_load_status()}


@router.post("/predict", response_model=MLInferenceResponse)
async def predict(
    task: MLTask = Form(...),
    file: UploadFile = File(...),
    confidence: float | None = Form(default=None),
    top_k: int | None = Form(default=None),
    _: dict = Depends(require_approved_doctor_or_admin),
) -> dict:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image uploads are allowed",
        )

    try:
        image_bytes = await file.read()
        return run_ml_inference(task, image_bytes, confidence=confidence, top_k=top_k)
    except MLServiceError as exc:
        return build_error_response(task, str(exc))
    except Exception as exc:
        return build_error_response(task, f"Inference failed: {exc}")
