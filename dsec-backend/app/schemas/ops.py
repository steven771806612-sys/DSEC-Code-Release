from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class RubricCreate(BaseModel):
    title: str
    version: str
    content: Optional[str] = None
    dimensions: list[dict] = []


class RubricOut(BaseModel):
    id: UUID
    title: str
    version: str
    content: Optional[str] = None
    dimensions: list = []
    is_active: bool
    created_at: datetime
    activated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PromptVersionCreate(BaseModel):
    prompt_type: str
    version: str
    content: str


class PromptVersionOut(BaseModel):
    id: UUID
    prompt_type: str
    version: str
    content: str
    is_active: bool
    is_canary: bool
    canary_percentage: float
    performance_metrics: dict = {}
    created_at: datetime
    activated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CanaryConfig(BaseModel):
    canary_percentage: float = Field(..., ge=0, le=100)


class DisagreementOut(BaseModel):
    id: UUID
    case_id: UUID
    case_page_id: Optional[UUID] = None
    ai_review_id: UUID
    human_review_id: UUID
    disagreement_type: Optional[str] = None
    ai_score: Optional[float] = None
    human_score: Optional[float] = None
    score_gap: Optional[float] = None
    severity: Optional[str] = None
    dimension: Optional[str] = None
    is_training_signal: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class VectorSearchRequest(BaseModel):
    query: str
    collection: str = "case_vectors"  # rubric_vectors / case_vectors / review_vectors
    top_k: int = Field(10, ge=1, le=50)
    industry: Optional[str] = None
    region: Optional[str] = None


class VectorSearchResult(BaseModel):
    id: UUID
    content: str
    similarity: float
    metadata: dict = {}


class DashboardMetrics(BaseModel):
    total_cases: int
    cases_by_status: dict
    ai_approval_rate: float
    major_disagreement_rate: float
    avg_review_latency_seconds: float
    total_vectors: dict
