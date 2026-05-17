"""Common/shared Pydantic schemas."""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, field_validator


class APIResponse(BaseModel):
    success: bool = True
    data: Optional[Any] = None
    error: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = None

    model_config = {"from_attributes": True}

    def __init__(self, **data):
        if data.get("timestamp") is None:
            from datetime import timezone
            data["timestamp"] = datetime.now(timezone.utc)
        super().__init__(**data)


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20

    @field_validator("page")
    @classmethod
    def page_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("page must be >= 1")
        return v

    @field_validator("page_size")
    @classmethod
    def page_size_range(cls, v: int) -> int:
        if not (1 <= v <= 100):
            raise ValueError("page_size must be between 1 and 100")
        return v

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedData(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    has_next: bool
