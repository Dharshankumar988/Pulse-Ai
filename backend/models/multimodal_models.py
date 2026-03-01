from typing import Literal

from pydantic import BaseModel, Field

RiskLevelType = Literal["low", "medium", "high"]


class MultimodalResponse(BaseModel):
    condition: str
    confidence: float
    risk_level: RiskLevelType
    recommendation: dict = Field(default_factory=dict)
    notes: str
    needs_image: bool = False
    needs_symptoms: bool = False
    follow_up_questions: list[str] = Field(default_factory=list)
    detections: list[dict] = Field(default_factory=list)
    image_width: int | None = None
    image_height: int | None = None
