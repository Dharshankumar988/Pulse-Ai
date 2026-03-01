from typing import Literal

from pydantic import BaseModel, EmailStr

RoleType = Literal["admin", "doctor"]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: RoleType = "doctor"
    specialty: str | None = None  # required for doctors, ignored for admins
    phone: str | None = None


class AuthUser(BaseModel):
    user_id: str
    email: EmailStr
    role: str
    status: str
    doctor_id: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: AuthUser
