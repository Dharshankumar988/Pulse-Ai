from typing import NoReturn

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from config.supabase_client import get_supabase_client
from dependencies.auth import require_admin, require_approved_doctor_or_admin
from models.medical_models import (
    DoctorCreate,
    DoctorUpdate,
    PatientCreate,
    PatientUpdate,
    RecordCreate,
    RecordUpdate,
)
from services.supabase_service import (
    SupabaseServiceError,
    delete_rows,
    insert_row,
    select_rows,
    update_rows,
    upload_image_and_get_public_url,
)

router = APIRouter(prefix="/api/v1", tags=["Medical"])


def _raise_server_error(exc: Exception) -> NoReturn:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/doctors")
def create_doctor(payload: DoctorCreate, _: dict = Depends(require_admin)) -> dict:
    try:
        data = insert_row("doctors", payload.model_dump())
        return {"data": data}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.get("/doctors")
def list_doctors(_: dict = Depends(require_admin)) -> dict:
    try:
        client = get_supabase_client()
        response = client.table("doctors").select("id,user_id,specialty,phone,users(full_name,email)").execute()
        rows = response.data or []
        normalized = []
        for row in rows:
            user_info = row.get("users") or {}
            if isinstance(user_info, list):
                user_info = user_info[0] if user_info else {}
            normalized.append(
                {
                    "id": row.get("id"),
                    "user_id": row.get("user_id"),
                    "full_name": user_info.get("full_name", "Unknown"),
                    "email": user_info.get("email"),
                    "specialty": row.get("specialty"),
                    "phone": row.get("phone"),
                }
            )
        return {"data": normalized, "count": len(normalized)}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)
    except Exception as exc:
        _raise_server_error(exc)


@router.get("/doctors/{doctor_id}")
def get_doctor(doctor_id: str, _: dict = Depends(require_admin)) -> dict:
    try:
        client = get_supabase_client()
        response = (
            client.table("doctors")
            .select("id,user_id,specialty,phone,users(full_name,email)")
            .eq("id", doctor_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        row = rows[0]
        user_info = row.get("users") or {}
        if isinstance(user_info, list):
            user_info = user_info[0] if user_info else {}
        return {
            "data": {
                "id": row.get("id"),
                "user_id": row.get("user_id"),
                "full_name": user_info.get("full_name", "Unknown"),
                "email": user_info.get("email"),
                "specialty": row.get("specialty"),
                "phone": row.get("phone"),
            }
        }
    except SupabaseServiceError as exc:
        _raise_server_error(exc)
    except Exception as exc:
        _raise_server_error(exc)


@router.put("/doctors/{doctor_id}")
def update_doctor(doctor_id: str, payload: DoctorUpdate, _: dict = Depends(require_admin)) -> dict:
    try:
        updates = payload.model_dump(exclude_none=True)
        rows = update_rows("doctors", {"id": doctor_id}, updates)
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        return {"data": rows[0]}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.delete("/doctors/{doctor_id}")
def delete_doctor(doctor_id: str, _: dict = Depends(require_admin)) -> dict:
    try:
        rows = delete_rows("doctors", {"id": doctor_id})
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        return {"data": rows[0]}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.post("/patients")
def create_patient(payload: PatientCreate, _: dict = Depends(require_approved_doctor_or_admin)) -> dict:
    try:
        if payload.email:
            existing = select_rows("patients", {"email": str(payload.email)})
            if existing:
                existing_id = existing[0].get("id", "unknown")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Patient with email '{payload.email}' already exists (ID: {existing_id}).",
                )
        data = insert_row("patients", payload.model_dump())
        return {"data": data}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.get("/patients")
def list_patients(_: dict = Depends(require_approved_doctor_or_admin)) -> dict:
    try:
        rows = select_rows("patients")
        return {"data": rows, "count": len(rows)}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.get("/patients/{patient_id}")
def get_patient(patient_id: str, _: dict = Depends(require_approved_doctor_or_admin)) -> dict:
    try:
        rows = select_rows("patients", {"id": patient_id})
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        return {"data": rows[0]}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.put("/patients/{patient_id}")
def update_patient(
    patient_id: str,
    payload: PatientUpdate,
    _: dict = Depends(require_approved_doctor_or_admin),
) -> dict:
    try:
        updates = payload.model_dump(exclude_none=True)
        rows = update_rows("patients", {"id": patient_id}, updates)
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        return {"data": rows[0]}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.delete("/patients/{patient_id}")
def delete_patient(patient_id: str, _: dict = Depends(require_approved_doctor_or_admin)) -> dict:
    try:
        rows = delete_rows("patients", {"id": patient_id})
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        return {"data": rows[0]}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.post("/records")
def create_record(payload: RecordCreate, _: dict = Depends(require_approved_doctor_or_admin)) -> dict:
    try:
        data = insert_row("records", payload.model_dump())
        return {"data": data}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.get("/records")
def list_records(_: dict = Depends(require_approved_doctor_or_admin)) -> dict:
    try:
        rows = select_rows("records")
        return {"data": rows, "count": len(rows)}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.get("/records/{record_id}")
def get_record(record_id: str, _: dict = Depends(require_approved_doctor_or_admin)) -> dict:
    try:
        rows = select_rows("records", {"id": record_id})
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
        return {"data": rows[0]}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.put("/records/{record_id}")
def update_record(
    record_id: str,
    payload: RecordUpdate,
    _: dict = Depends(require_approved_doctor_or_admin),
) -> dict:
    try:
        updates = payload.model_dump(exclude_none=True)
        rows = update_rows("records", {"id": record_id}, updates)
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
        return {"data": rows[0]}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.delete("/records/{record_id}")
def delete_record(record_id: str, _: dict = Depends(require_approved_doctor_or_admin)) -> dict:
    try:
        rows = delete_rows("records", {"id": record_id})
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
        return {"data": rows[0]}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.post("/records/{record_id}/image")
async def upload_record_image(
    record_id: str,
    file: UploadFile = File(...),
    _: dict = Depends(require_approved_doctor_or_admin),
) -> dict:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only image uploads are allowed")

    try:
        file_bytes = await file.read()
        public_url = upload_image_and_get_public_url(
            file_bytes=file_bytes,
            filename=file.filename or "record-image",
            content_type=file.content_type,
            folder="records",
        )
        updated_rows = update_rows("records", {"id": record_id}, {"image_url": public_url})
        if not updated_rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
        return {"public_url": public_url, "record": updated_rows[0]}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)
