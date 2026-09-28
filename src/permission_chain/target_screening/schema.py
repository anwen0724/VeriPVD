from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Classification = Literal["permission_relevant", "uncertain", "non_permission"]
Confidence = Literal["high", "medium", "low"]


class ScreeningDecision(BaseModel):
    target_group_id: str
    classification: Classification
    confidence: Confidence
    reason: str = Field(min_length=1, max_length=2000)


class ScreeningBatchResponse(BaseModel):
    decisions: list[ScreeningDecision] = Field(default_factory=list)
