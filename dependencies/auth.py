from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from services.auth_service import AuthServiceError, ensure_approved, validate_access_token

bearer_scheme = HTTPBearer(auto_error=True)


def get_current_profile(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    token = credentials.credentials
    try:
        return validate_access_token(token)
    except AuthServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


def require_approved_doctor_or_admin(profile: dict = Depends(get_current_profile)) -> dict:
    role = profile.get("role")
    if role not in {"doctor", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    ensure_approved(profile)
    return profile


def require_admin(profile: dict = Depends(get_current_profile)) -> dict:
    if profile.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    ensure_approved(profile)
    return profile
