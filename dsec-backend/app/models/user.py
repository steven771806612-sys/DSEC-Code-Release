import enum
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, String, Text, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class RoleEnum(str, enum.Enum):
    AGENT = "agent"
    PLATFORM_REVIEWER = "platform_reviewer"
    DJI_SE = "dji_se"
    ADMIN = "admin"


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[Optional[str]] = mapped_column(String(50))
    tier: Mapped[Optional[str]] = mapped_column(
        String(20)
    )  # gold / silver / bronze
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="org")
    departments: Mapped[list["Department"]] = relationship(
        "Department", back_populates="org"
    )
    cases: Mapped[list["Case"]] = relationship("Case", back_populates="org")  # noqa


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_dji_internal: Mapped[bool] = mapped_column(Boolean, default=False)

    org: Mapped["Org"] = relationship("Org", back_populates="departments")
    users: Mapped[list["User"]] = relationship("User", back_populates="department")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False
    )
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    role: Mapped[RoleEnum] = mapped_column(
        Enum(RoleEnum, name="role_enum"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    org: Mapped["Org"] = relationship("Org", back_populates="users")
    department: Mapped[Optional["Department"]] = relationship(
        "Department", back_populates="users"
    )

    def is_dji_staff(self) -> bool:
        return self.role in (RoleEnum.DJI_SE, RoleEnum.ADMIN)
