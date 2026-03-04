from fastapi import APIRouter, Depends, HTTPException, status

from models.auth_models import LoginRequest, LoginResponse, RegisterRequest
from services.auth_service import AuthServiceError, login_user, register_user
from dependencies.auth import get_current_profile

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> dict:
    try:
        return login_user(payload.email, payload.password)
    except AuthServiceError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/register")
def register(payload: RegisterRequest) -> dict:
    try:
        return register_user(
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            role=payload.role,
            specialty=payload.specialty,
            phone=payload.phone,
        )
    except AuthServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/validate")
def validate_token(profile: dict = Depends(get_current_profile)) -> dict:
    return {"authenticated": True, "user": profile}
