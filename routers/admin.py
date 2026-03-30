from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, status

from config.supabase_client import get_supabase_client
from dependencies.auth import require_admin
from services.supabase_service import SupabaseServiceError, update_rows

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


def _raise_server_error(exc: Exception) -> NoReturn:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/pending")
def list_pending_users(_: dict = Depends(require_admin)) -> dict:
    """List ALL pending registrations — both doctors and admin prospects."""
    try:
        client = get_supabase_client()
        # Fetch all pending users (any role), left-join doctors for specialty
        response = (
            client.table("users")
            .select("id, email, full_name, role, status, created_at, doctors(id, specialty, phone)")
            .eq("status", "pending")
            .execute()
        )
        rows = response.data or []

        # Flatten for the frontend
        result = []
        for row in rows:
            doctor_info = row.get("doctors")
            if isinstance(doctor_info, list):
                doctor_info = doctor_info[0] if doctor_info else {}
            elif doctor_info is None:
                doctor_info = {}

            result.append({
                "user_id": row["id"],
                "doctor_id": doctor_info.get("id"),
                "email": row["email"],
                "full_name": row["full_name"],
                "role": row["role"],
                "specialty": doctor_info.get("specialty", "N/A") if row["role"] == "doctor" else "—",
                "phone": doctor_info.get("phone"),
                "status": row["status"],
                "created_at": row["created_at"],
            })

        return {"data": result, "count": len(result)}
    except Exception as exc:
        _raise_server_error(exc)


# Keep old endpoint as alias for backwards compatibility
@router.get("/doctors/pending")
def list_pending_doctors(admin: dict = Depends(require_admin)) -> dict:
    """Alias: same as /pending but only doctors."""
    try:
        client = get_supabase_client()
        response = (
            client.table("users")
            .select("id, email, full_name, role, status, created_at, doctors(id, specialty, phone)")
            .eq("status", "pending")
            .eq("role", "doctor")
            .execute()
        )
        rows = response.data or []

        result = []
        for row in rows:
            doctor_info = row.get("doctors")
            if isinstance(doctor_info, list):
                doctor_info = doctor_info[0] if doctor_info else {}
            elif doctor_info is None:
                doctor_info = {}

            result.append({
                "user_id": row["id"],
                "doctor_id": doctor_info.get("id"),
                "email": row["email"],
                "full_name": row["full_name"],
                "role": row["role"],
                "specialty": doctor_info.get("specialty", "N/A"),
                "phone": doctor_info.get("phone"),
                "status": row["status"],
                "created_at": row["created_at"],
            })

        return {"data": result, "count": len(result)}
    except Exception as exc:
        _raise_server_error(exc)


@router.post("/users/{user_id}/approve")
def approve_user(user_id: str, _: dict = Depends(require_admin)) -> dict:
    """Approve any pending user (doctor OR admin prospect)."""
    try:
        rows = update_rows("users", {"id": user_id}, {"status": "approved"})
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return {"data": rows[0], "message": f"{rows[0].get('role', 'user').title()} approved"}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


@router.post("/users/{user_id}/reject")
def reject_user(user_id: str, _: dict = Depends(require_admin)) -> dict:
    """Reject any pending user (doctor OR admin prospect)."""
    try:
        rows = update_rows("users", {"id": user_id}, {"status": "rejected"})
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return {"data": rows[0], "message": f"{rows[0].get('role', 'user').title()} rejected"}
    except SupabaseServiceError as exc:
        _raise_server_error(exc)


# Keep old endpoints as aliases
@router.post("/doctors/{user_id}/approve")
def approve_doctor(user_id: str, admin: dict = Depends(require_admin)) -> dict:
    return approve_user(user_id, admin)


@router.post("/doctors/{user_id}/reject")
def reject_doctor(user_id: str, admin: dict = Depends(require_admin)) -> dict:
    return reject_user(user_id, admin)
