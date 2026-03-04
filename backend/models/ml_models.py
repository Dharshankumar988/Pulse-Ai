from typing import Literal

from pydantic import BaseModel, Field

MLTask = Literal[
    "fracture",
    "tumor",
    "kidney_stone",
    "skin_classification",
    "image_type_classification",
]


class PredictionItem(BaseModel):
    label: str
    confidence: float
    bbox: list[float] | None = None


class MLInferenceResponse(BaseModel):
    success: bool
    task: MLTask
    model_name: str
    model_type: Literal["yolo", "classifier"]
    predictions: list[PredictionItem] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    error: str | None = None
