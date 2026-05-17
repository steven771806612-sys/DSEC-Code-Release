import enum
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ReviewTypeEnum(str, enum.Enum):
    AI = "ai"
    PLATFORM = "platform"
    DJI = "dji"


class TaskStatusEnum(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class DecisionEnum(str, enum.Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REVISE = "revise"
    PENDING = "pending"


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    review_type: Mapped[ReviewTypeEnum] = mapped_column(
        Enum(ReviewTypeEnum, name="review_type_enum"), nullable=False
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[TaskStatusEnum] = mapped_column(
        Enum(TaskStatusEnum, name="task_status_enum"),
        default=TaskStatusEnum.PENDING,
    )
    priority: Mapped[int] = mapped_column(Integer, default=3)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    case: Mapped["Case"] = relationship("Case", back_populates="review_tasks")  # noqa
    assignee: Mapped[Optional["User"]] = relationship(  # noqa
        "User", foreign_keys=[assigned_to]
    )
    review: Mapped[Optional["Review"]] = relationship(
        "Review", back_populates="task", uselist=False
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    case_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_versions.id"), nullable=False
    )
    review_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_tasks.id"), nullable=False
    )
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )  # NULL = AI
    review_type: Mapped[ReviewTypeEnum] = mapped_column(
        Enum(ReviewTypeEnum, name="review_type_enum"), nullable=False
    )
    overall_score: Mapped[Optional[float]] = mapped_column(Float)
    dimension_scores: Mapped[dict] = mapped_column(JSONB, default=dict)
    issues: Mapped[list] = mapped_column(JSONB, default=list)
    recommendations: Mapped[list] = mapped_column(JSONB, default=list)
    decision: Mapped[Optional[DecisionEnum]] = mapped_column(
        Enum(DecisionEnum, name="decision_enum")
    )
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    is_override: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[Optional[str]] = mapped_column(Text)
    raw_llm_output: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    case: Mapped["Case"] = relationship("Case", back_populates="reviews")  # noqa
    task: Mapped["ReviewTask"] = relationship("ReviewTask", back_populates="review")
    reviewer: Mapped[Optional["User"]] = relationship(  # noqa
        "User", foreign_keys=[reviewer_id]
    )
    case_version: Mapped["CaseVersion"] = relationship(  # noqa
        "CaseVersion", foreign_keys=[case_version_id]
    )
