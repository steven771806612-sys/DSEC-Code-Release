from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class DimensionScoreOut(BaseModel):
    dimension: str
    score: Optional[float] = Field(None, ge=0, le=100)
    evidence: str = ""
    issues: list[str] = []
    recommendations: list[str] = []


class ReviewOut(BaseModel):
    id: UUID
    case_id: UUID
    review_type: str
    reviewer_id: Optional[UUID] = None
    overall_score: Optional[float] = None
    dimension_scores: dict = {}
    issues: list = []
    recommendations: list = []
    decision: Optional[str] = None
    confidence: Optional[float] = None
    is_override: bool = False
    override_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReviewTaskOut(BaseModel):
    id: UUID
    case_id: UUID
    review_type: str
    assigned_to: Optional[UUID] = None
    status: str
    priority: int
    due_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    sla_breached: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PlatformReviewSubmit(BaseModel):
    overall_score: Optional[float] = Field(None, ge=0, le=100)
    dimension_scores: dict = {}
    issues: list[dict] = []
    recommendations: list[str] = []
    decision: str  # approve / reject / revise
    is_override: bool = False
    override_reason: Optional[str] = None


class DJIReviewSubmit(BaseModel):
    overall_score: float = Field(..., ge=0, le=100)
    dimension_scores: dict = {}
    issues: list[dict] = []
    recommendations: list[str] = []
    decision: str  # approve / reject
    override_reason: Optional[str] = None


class OverrideRequest(BaseModel):
    overall_score: Optional[float] = Field(None, ge=0, le=100)
    decision: Optional[str] = None
    override_reason: str = Field(..., min_length=10)


class AIReviewTrigger(BaseModel):
    force: bool = False  # re-run even if already reviewed
