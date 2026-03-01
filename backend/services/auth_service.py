from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status

from config.settings import settings
from config.supabase_client import get_supabase_client


class AuthServiceError(RuntimeError):
    pass


# ── JWT helpers ───────────────────────────────────────────

def _create_access_token(payload: dict) -> str:
    """Create a signed JWT with an expiration claim."""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiration_hours)
    to_encode = {**payload, "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode_access_token(token: str) -> dict:
    """Decode and verify a JWT. Raises on expiry or bad signature."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise AuthServiceError("Token has expired")
    except jwt.InvalidTokenError as exc:
        raise AuthServiceError(f"Invalid token: {exc}")


# ── Profile lookups ───────────────────────────────────────

def get_profile_by_email(email: str) -> dict:
    """Look up user profile from the users table (covers admins AND doctors)."""
    client = get_supabase_client()
    response = client.table("users").select("id,email,role,status,full_name,password").eq("email", email).limit(1).execute()
    rows = response.data or []
    if not rows:
        raise AuthServiceError("No user profile found")
    return rows[0]


def get_doctor_profile_by_user_id(user_id: str) -> dict | None:
    """Look up doctor-specific profile (specialty, phone) by user_id. Returns None for admins."""
    client = get_supabase_client()
    response = client.table("doctors").select("id,user_id,specialty,phone").eq("user_id", user_id).limit(1).execute()
    rows = response.data or []
    return rows[0] if rows else None


def _build_user_response(profile: dict) -> dict:
    """Build the user info dict, optionally including doctor_id."""
    doctor_id = None
    if profile.get("role") == "doctor":
        doctor_profile = get_doctor_profile_by_user_id(profile["id"])
        if doctor_profile:
            doctor_id = doctor_profile.get("id")
    return {
        "user_id": profile["id"],
        "email": profile["email"],
        "role": profile.get("role", "doctor"),
        "status": profile.get("status", "pending"),
        "doctor_id": doctor_id,
    }


# ── Login ─────────────────────────────────────────────────

def login_user(email: str, password: str) -> dict:
    """Authenticate against the users table and return a JWT."""
    try:
        profile = get_profile_by_email(email)

        # Verify password (plain text comparison)
        stored_password = profile.get("password", "")
        if password != stored_password:
            raise AuthServiceError("Invalid email or password")

        # Check approval status
        if profile.get("status") != "approved":
            raise AuthServiceError("Account is not yet approved by an admin")

        # Build JWT
        token_payload = {
            "sub": profile["id"],
            "email": profile["email"],
            "role": profile.get("role", "doctor"),
        }
        access_token = _create_access_token(token_payload)

        return {
            "access_token": access_token,
            "refresh_token": None,
            "user": _build_user_response(profile),
        }
    except AuthServiceError:
        raise
    except Exception as exc:
        raise AuthServiceError(f"Login failed: {exc}") from exc


# ── Token validation ──────────────────────────────────────

def validate_access_token(token: str) -> dict:
    """Decode a JWT and return the user profile from the DB."""
    try:
        claims = _decode_access_token(token)
        email = claims.get("email")
        if not email:
            raise AuthServiceError("Token missing email claim")

        profile = get_profile_by_email(email)
        return _build_user_response(profile)
    except AuthServiceError:
        raise
    except Exception as exc:
        raise AuthServiceError(f"Token validation failed: {exc}") from exc


def ensure_approved(profile: dict) -> None:
    if profile.get("status") != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not approved",
        )


# ── Registration ──────────────────────────────────────────

def register_user(
    email: str,
    password: str,
    full_name: str,
    role: str = "doctor",
    specialty: str | None = None,
    phone: str | None = None,
) -> dict:
    """Register a new user (doctor or admin).

    - Both roles get a row in public.users with status=pending.
    - Doctors additionally get a row in public.doctors for specialty/phone.
    - Admins only need approval from an existing admin to become active.
    """
    try:
        if role == "doctor" and not specialty:
            raise AuthServiceError("Specialty is required for doctor registration")

        client = get_supabase_client()

        # 1. Insert into public.users
        user_payload = {
            "email": email,
            "full_name": full_name,
            "password": password,
            "role": role,
            "status": "pending",
        }
        user_resp = client.table("users").insert(user_payload).execute()
        user_rows = user_resp.data or []
        if not user_rows:
            raise AuthServiceError("Failed to create user profile")

        new_user_id = user_rows[0].get("id", "")
        result = {
            "message": "Registration successful. Please wait for admin approval before logging in.",
            "user_id": new_user_id,
            "email": email,
            "role": role,
            "status": "pending",
        }

        # 2. For doctors, also create the doctor-specific profile
        if role == "doctor":
            doctor_payload = {
                "user_id": new_user_id,
                "specialty": specialty,
                "phone": phone,
            }
            doctor_resp = client.table("doctors").insert(doctor_payload).execute()
            doctor_rows = doctor_resp.data or []
            if not doctor_rows:
                raise AuthServiceError("Failed to create doctor profile")
            result["doctor_id"] = doctor_rows[0].get("id", "")

        return result
    except AuthServiceError:
        raise
    except Exception as exc:
        raise AuthServiceError(f"Registration failed: {exc}") from exc
