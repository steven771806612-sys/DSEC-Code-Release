from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=512)
    industry: Optional[str] = None
    region: Optional[str] = None
    tags: list[str] = []


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=512)
    industry: Optional[str] = None
    region: Optional[str] = None
    tags: Optional[list[str]] = None


class CaseOut(BaseModel):
    id: UUID
    org_id: UUID
    created_by: UUID
    title: str
    industry: Optional[str] = None
    region: Optional[str] = None
    status: str
    rubric_version: str
    tags: list[str] = []
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    current_version_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


class CasePageCreate(BaseModel):
    page_number: int = Field(..., ge=1)
    page_type: Optional[str] = None
    title: Optional[str] = None
    content_text: Optional[str] = None
    content_html: Optional[str] = None
    has_images: bool = False


class CasePageUpdate(BaseModel):
    page_type: Optional[str] = None
    title: Optional[str] = None
    content_text: Optional[str] = None
    content_html: Optional[str] = None
    has_images: Optional[bool] = None


class CasePageOut(BaseModel):
    id: UUID
    case_id: UUID
    case_version_id: UUID
    page_number: int
    page_type: Optional[str] = None
    title: Optional[str] = None
    content_text: Optional[str] = None
    word_count: int
    has_images: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseVersionOut(BaseModel):
    id: UUID
    case_id: UUID
    version_number: int
    submitted_by: UUID
    change_summary: Optional[str] = None
    is_current: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AttachmentOut(BaseModel):
    id: UUID
    case_id: UUID
    file_name: str
    file_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    is_primary: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AttachmentUploadRequest(BaseModel):
    file_name: str
    file_type: str
    file_size_bytes: Optional[int] = None
    is_primary: bool = False


class PresignedUploadResponse(BaseModel):
    attachment_id: UUID
    upload_url: str
    s3_key: str
    expires_in: int  # seconds


class CaseSubmitRequest(BaseModel):
    change_summary: Optional[str] = None


class CaseWithdrawRequest(BaseModel):
    reason: Optional[str] = None


class CaseListFilter(BaseModel):
    status: Optional[str] = None
    industry: Optional[str] = None
    region: Optional[str] = None
    search: Optional[str] = None
