from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from dependencies.auth import require_admin
from models.supabase_models import InsertRequest, SelectRequest, UpdateRequest
from services.supabase_service import (
    SupabaseServiceError,
    insert_row,
    select_rows,
    update_rows,
    upload_image_and_get_public_url,
)

router = APIRouter(prefix="/api/v1/supabase", tags=["Supabase"])


@router.post("/select")
def select_data(request: SelectRequest, _: dict = Depends(require_admin)) -> dict:
    try:
        rows = select_rows(request.table, request.filters, request.columns)
        return {"data": rows, "count": len(rows)}
    except SupabaseServiceError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/insert")
def insert_data(request: InsertRequest, _: dict = Depends(require_admin)) -> dict:
    try:
        created = insert_row(request.table, request.payload)
        return {"data": created}
    except SupabaseServiceError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/update")
def update_data(request: UpdateRequest, _: dict = Depends(require_admin)) -> dict:
    try:
        updated = update_rows(request.table, request.match_filters, request.updates)
        return {"data": updated, "count": len(updated)}
    except SupabaseServiceError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    folder: str = Form("records"),
    _: dict = Depends(require_admin),
) -> dict:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image uploads are allowed",
        )

    try:
        file_bytes = await file.read()
        public_url = upload_image_and_get_public_url(
            file_bytes=file_bytes,
            filename=file.filename or "image",
            content_type=file.content_type,
            folder=folder,
        )
        return {"public_url": public_url}
    except SupabaseServiceError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
