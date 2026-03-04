from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, status

from config.supabase_client import get_supabase_client
from dependencies.auth import require_approved_doctor_or_admin
from models.medical_models import PatientCreate, PatientUpdate
from models.patient_management_models import AnalysisResultCreate, PatientDoctorLinkCreate
from services.supabase_service import SupabaseServiceError, delete_rows, insert_row, select_rows, update_rows

router = APIRouter(prefix="/api/v1/patient-management", tags=["PatientManagement"])


def _raise_server_error(exc: Exception) -> NoReturn:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.post("/patients")
def create_patient(payload: PatientCreate, profile: dict = Depends(require_approved_doctor_or_admin)) -> dict:
    try:
        if payload.email:
            existing = select_rows("patients", {"email": str(payload.email)})
            if existing:
                existing_id = existing[0].get("id", "unknown")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Patient with email '{payload.email}' already exists (ID: {existing_id}).",
                )
        created = insert_row("patients", payload.model_dump())

        if profile.get("role") == "doctor" and profile.get("doctor_id") and created.get("id"):
            doctor_id = profile.get("doctor_id")
            patient_id = created.get("id")
            existing_link = select_rows("patient_doctors", {"patient_id": patient_id, "doctor_id": doctor_id})
            if not existing_link:
                insert_row("patient_doctors", {"patient_id": patient_id, "doctor_id": doctor_id})

        return {"data": created}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.get("/patients")
def list_patients(name: str | None = None, profile: dict = Depends(require_approved_doctor_or_admin)) -> dict:
    try:
        rows = select_rows("patients")
        role = profile.get("role")
        doctor_id = profile.get("doctor_id")

        if role == "doctor" and doctor_id:
            linked = select_rows("patient_doctors", {"doctor_id": doctor_id})
            analyzed = select_rows("analysis_results", {"doctor_id": doctor_id})
            stored_records = select_rows("records", {"doctor_id": doctor_id})

            visible_patient_ids = {
                row.get("patient_id")
                for row in [*linked, *analyzed, *stored_records]
                if row.get("patient_id")
            }
            rows = [row for row in rows if row.get("id") in visible_patient_ids]
        elif role == "doctor":
            rows = []

        if name:
            needle = name.strip().lower()
            rows = [row for row in rows if needle in str(row.get("full_name") or "").lower()]

        rows.sort(key=lambda item: str(item.get("full_name") or "").lower())
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
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

    try:
        updated_rows = update_rows("patients", {"id": patient_id}, updates)
        if not updated_rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        return {"data": updated_rows[0]}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.delete("/patients/{patient_id}")
def delete_patient(patient_id: str, _: dict = Depends(require_approved_doctor_or_admin)) -> dict:
    try:
        delete_rows("analysis_results", {"patient_id": patient_id})
        delete_rows("records", {"patient_id": patient_id})
        delete_rows("patient_doctors", {"patient_id": patient_id})

        deleted_rows = delete_rows("patients", {"id": patient_id})
        if not deleted_rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
        return {"data": deleted_rows[0]}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.post("/link")
def link_patient_to_doctor(payload: PatientDoctorLinkCreate, _: dict = Depends(require_approved_doctor_or_admin)) -> dict:
    try:
        existing = select_rows(
            "patient_doctors",
            {"patient_id": payload.patient_id, "doctor_id": payload.doctor_id},
        )
        if existing:
            return {"data": existing[0], "message": "Link already exists"}

        linked = insert_row("patient_doctors", payload.model_dump())
        return {"data": linked}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.get("/patients/{patient_id}/doctors")
def list_patient_doctors(patient_id: str, _: dict = Depends(require_approved_doctor_or_admin)) -> dict:
    try:
        links = select_rows("patient_doctors", {"patient_id": patient_id})
        doctor_ids = [link.get("doctor_id") for link in links if link.get("doctor_id")]
        doctors: list[dict[str, Any]] = []
        client = get_supabase_client()
        for doctor_id in doctor_ids:
            # Join doctors → users via FK to get full_name + email
            resp = (
                client.table("doctors")
                .select("id, user_id, specialty, phone, users(full_name, email)")
                .eq("id", doctor_id)
                .limit(1)
                .execute()
            )
            rows = resp.data or []
            if rows:
                row = rows[0]
                user_info = row.get("users") or {}
                if isinstance(user_info, list):
                    user_info = user_info[0] if user_info else {}
                doctors.append({
                    "id": row["id"],
                    "full_name": user_info.get("full_name", "Unknown"),
                    "email": user_info.get("email"),
                    "specialty": row.get("specialty"),
                    "phone": row.get("phone"),
                })

        return {"data": doctors, "count": len(doctors)}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.post("/analysis")
def store_analysis_result(payload: AnalysisResultCreate, profile: dict = Depends(require_approved_doctor_or_admin)) -> dict:
    try:
        effective_doctor_id = payload.doctor_id
        if profile.get("role") == "doctor" and profile.get("doctor_id"):
            effective_doctor_id = profile.get("doctor_id")

        existing = select_rows(
            "patient_doctors",
            {"patient_id": payload.patient_id, "doctor_id": effective_doctor_id},
        )
        if not existing:
            insert_row(
                "patient_doctors",
                {"patient_id": payload.patient_id, "doctor_id": effective_doctor_id},
            )

        analysis_payload = payload.model_dump()
        analysis_payload["doctor_id"] = effective_doctor_id
        created = insert_row("analysis_results", analysis_payload)
        return {"data": created}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.get("/patients/{patient_id}/history")
def get_patient_history(
    patient_id: str,
    order: str = "desc",
    _: dict = Depends(require_approved_doctor_or_admin),
) -> dict:
    sort_desc = order.lower() != "asc"

    try:
        records = select_rows("records", {"patient_id": patient_id})
        analyses = select_rows("analysis_results", {"patient_id": patient_id})

        history: list[dict] = []
        for record in records:
            history.append(
                {
                    "entry_type": "record",
                    "timestamp": record.get("recorded_at") or record.get("created_at"),
                    "data": record,
                }
            )

        for analysis in analyses:
            history.append(
                {
                    "entry_type": "analysis",
                    "timestamp": analysis.get("created_at"),
                    "data": analysis,
                }
            )

        history.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=sort_desc)

        return {
            "data": history,
            "count": len(history),
            "order": "desc" if sort_desc else "asc",
        }
    except SupabaseServiceError as exc:
        _raise_server_error(exc)
