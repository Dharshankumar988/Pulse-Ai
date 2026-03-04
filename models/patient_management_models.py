from typing import Literal

from pydantic import BaseModel, Field

SeverityType = Literal["low", "moderate", "high", "critical"]
RiskType = Literal["low", "medium", "high"]


class PatientDoctorLinkCreate(BaseModel):
    patient_id: str
    doctor_id: str


class AnalysisResultCreate(BaseModel):
    patient_id: str
    doctor_id: str
    disease: str
    probability: float = Field(..., ge=0.0, le=1.0)
    severity: SeverityType
    risk: RiskType
    uncertainty: float = Field(..., ge=0.0, le=1.0)
    recommendations: dict = Field(default_factory=dict)
    follow_up_questions: list[str] = Field(default_factory=list)
    sources: dict = Field(default_factory=dict)
    notes: str | None = None
