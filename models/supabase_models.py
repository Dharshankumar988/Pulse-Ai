from typing import Any

from pydantic import BaseModel, Field


class SelectRequest(BaseModel):
    table: str = Field(..., min_length=1)
    filters: dict[str, Any] = Field(default_factory=dict)
    columns: str = "*"


class InsertRequest(BaseModel):
    table: str = Field(..., min_length=1)
    payload: dict[str, Any]


class UpdateRequest(BaseModel):
    table: str = Field(..., min_length=1)
    match_filters: dict[str, Any]
    updates: dict[str, Any]
