from typing import Literal

from pydantic import BaseModel, Field

RiskLevelType = Literal["low", "medium", "high"]
ResponseType = Literal["analysis", "chat"]


class MultimodalResponse(BaseModel):
    response_type: ResponseType = "analysis"
    chat_response: str = ""
    condition: str = ""
    confidence: float = 0.0
    risk_level: RiskLevelType = "low"
    recommendation: dict = Field(default_factory=dict)
    notes: str = ""
    needs_image: bool = False
    needs_symptoms: bool = False
    follow_up_questions: list[str] = Field(default_factory=list)
    detections: list[dict] = Field(default_factory=list)
    image_width: int | None = None
    image_height: int | None = None
    routed_task: str = ""
    model_name: str = ""
