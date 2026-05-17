import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

# pgvector import — graceful fallback if not available in dev
try:
    from pgvector.sqlalchemy import Vector
    VECTOR_TYPE = Vector(1536)
except ImportError:
    from sqlalchemy import Text as Vector
    VECTOR_TYPE = Text()


class RubricVector(Base):
    __tablename__ = "rubric_vectors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(VECTOR_TYPE)
    rubric_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rubrics.id"), nullable=True
    )
    dimension: Mapped[Optional[str]] = mapped_column(String(200))
    version: Mapped[Optional[str]] = mapped_column(String(20))
    industry: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    region: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    rubric: Mapped[Optional["Rubric"]] = relationship("Rubric", back_populates="vectors")


class CaseVector(Base):
    __tablename__ = "case_vectors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(VECTOR_TYPE)
    case_page_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_pages.id"), nullable=True
    )
    case_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True
    )
    page_type: Mapped[Optional[str]] = mapped_column(String(50))
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    region: Mapped[Optional[str]] = mapped_column(String(50))
    overall_score: Mapped[Optional[float]] = mapped_column(Float)
    label_source: Mapped[Optional[str]] = mapped_column(String(20))  # dji/platform/ai
    status: Mapped[Optional[str]] = mapped_column(String(20))  # approved/rejected
    rubric_version: Mapped[Optional[str]] = mapped_column(String(20))
    is_correction: Mapped[bool] = mapped_column(Boolean, default=False)
    weight_boost: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ReviewVector(Base):
    __tablename__ = "review_vectors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(VECTOR_TYPE)
    review_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id"), nullable=True
    )
    review_type: Mapped[Optional[str]] = mapped_column(String(20))
    dimension: Mapped[Optional[str]] = mapped_column(String(200))
    decision: Mapped[Optional[str]] = mapped_column(String(20))
    score: Mapped[Optional[float]] = mapped_column(Float)
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DisagreementVector(Base):
    __tablename__ = "disagreement_vectors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(VECTOR_TYPE)
    disagreement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("disagreement_records.id"), nullable=True
    )
    dimension: Mapped[Optional[str]] = mapped_column(String(200))
    severity: Mapped[Optional[str]] = mapped_column(String(20))
    is_correction: Mapped[bool] = mapped_column(Boolean, default=True)
    weight_boost: Mapped[float] = mapped_column(Float, default=1.5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Rubric(Base):
    __tablename__ = "rubrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    dimensions: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    vectors: Mapped[list["RubricVector"]] = relationship(
        "RubricVector", back_populates="rubric"
    )
    creator: Mapped[Optional["User"]] = relationship(  # noqa
        "User", foreign_keys=[created_by]
    )


class DisagreementRecord(Base):
    __tablename__ = "disagreement_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    case_page_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_pages.id"), nullable=True
    )
    ai_review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id"), nullable=False
    )
    human_review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id"), nullable=False
    )
    disagreement_type: Mapped[Optional[str]] = mapped_column(String(50))
    # score_gap / decision_flip / issue_miss
    ai_score: Mapped[Optional[float]] = mapped_column(Float)
    human_score: Mapped[Optional[float]] = mapped_column(Float)
    score_gap: Mapped[Optional[float]] = mapped_column(Float)
    severity: Mapped[Optional[str]] = mapped_column(String(20))
    # minor / major / critical
    dimension: Mapped[Optional[str]] = mapped_column(String(200))
    ai_reasoning: Mapped[Optional[str]] = mapped_column(Text)
    human_reasoning: Mapped[Optional[str]] = mapped_column(Text)
    is_training_signal: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    ai_review: Mapped["Review"] = relationship("Review", foreign_keys=[ai_review_id])  # noqa
    human_review: Mapped["Review"] = relationship(  # noqa
        "Review", foreign_keys=[human_review_id]
    )


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    prompt_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # system / evaluation / summary
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_canary: Mapped[bool] = mapped_column(Boolean, default=False)
    canary_percentage: Mapped[float] = mapped_column(Float, default=0.0)
    performance_metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deprecated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    creator: Mapped[Optional["User"]] = relationship(  # noqa
        "User", foreign_keys=[created_by]
    )
