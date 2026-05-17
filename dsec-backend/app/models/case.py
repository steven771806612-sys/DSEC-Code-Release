import enum
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class CaseStatusEnum(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    AI_REVIEWED = "AI_REVIEWED"
    PLATFORM_REVIEWED = "PLATFORM_REVIEWED"
    DJI_REVIEWED = "DJI_REVIEWED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PageTypeEnum(str, enum.Enum):
    OVERVIEW = "overview"
    ARCHITECTURE = "architecture"
    DEPLOYMENT = "deployment"
    RESULTS = "results"
    APPENDIX = "appendix"


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    region: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[CaseStatusEnum] = mapped_column(
        Enum(CaseStatusEnum, name="case_status_enum"),
        default=CaseStatusEnum.DRAFT,
        nullable=False,
        index=True,
    )
    current_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    rubric_version: Mapped[str] = mapped_column(String(20), default="v1.0")
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    org: Mapped["Org"] = relationship("Org", back_populates="cases")  # noqa
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])  # noqa
    versions: Mapped[list["CaseVersion"]] = relationship(
        "CaseVersion", back_populates="case", order_by="CaseVersion.version_number"
    )
    pages: Mapped[list["CasePage"]] = relationship("CasePage", back_populates="case")
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment", back_populates="case"
    )
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="case")  # noqa
    review_tasks: Mapped[list["ReviewTask"]] = relationship(  # noqa
        "ReviewTask", back_populates="case"
    )


class CaseVersion(Base):
    __tablename__ = "case_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    change_summary: Mapped[Optional[str]] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    case: Mapped["Case"] = relationship("Case", back_populates="versions")
    submitter: Mapped["User"] = relationship("User", foreign_keys=[submitted_by])  # noqa
    pages: Mapped[list["CasePage"]] = relationship(
        "CasePage", back_populates="version"
    )


class CasePage(Base):
    __tablename__ = "case_pages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    case_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_versions.id"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_type: Mapped[Optional[PageTypeEnum]] = mapped_column(
        Enum(PageTypeEnum, name="page_type_enum")
    )
    title: Mapped[Optional[str]] = mapped_column(String(512))
    content_text: Mapped[Optional[str]] = mapped_column(Text)
    content_html: Mapped[Optional[str]] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    has_images: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    case: Mapped["Case"] = relationship("Case", back_populates="pages")
    version: Mapped["CaseVersion"] = relationship("CaseVersion", back_populates="pages")


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    case_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("case_versions.id"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[Optional[str]] = mapped_column(String(50))
    s3_key: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    case: Mapped["Case"] = relationship("Case", back_populates="attachments")
    uploader: Mapped["User"] = relationship("User", foreign_keys=[uploaded_by])  # noqa
