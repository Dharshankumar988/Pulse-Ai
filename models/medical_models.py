from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr


StatusType = Literal["pending", "approved", "rejected"]
RoleType = Literal["admin", "doctor"]


class DoctorCreate(BaseModel):
    user_id: str
    specialty: str
    phone: str | None = None


class DoctorUpdate(BaseModel):
    specialty: str | None = None
    phone: str | None = None


class PatientCreate(BaseModel):
    full_name: str
    date_of_birth: date | None = None
    email: EmailStr | None = None
    phone: str | None = None


class PatientUpdate(BaseModel):
    full_name: str | None = None
    date_of_birth: date | None = None
    email: EmailStr | None = None
    phone: str | None = None


class RecordCreate(BaseModel):
    doctor_id: str
    patient_id: str
    diagnosis: str
    notes: str | None = None
    image_url: str | None = None
    status: StatusType = "pending"


class RecordUpdate(BaseModel):
    diagnosis: str | None = None
    notes: str | None = None
    image_url: str | None = None
    status: StatusType | None = None
