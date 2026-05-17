# Models package — import all models so Alembic can detect them
from app.models.user import Org, Department, User, RoleEnum
from app.models.case import Case, CaseVersion, CasePage, Attachment, CaseStatusEnum, PageTypeEnum
from app.models.review import Review, ReviewTask, ReviewTypeEnum, TaskStatusEnum, DecisionEnum
from app.models.rag import (
    Rubric, RubricVector, CaseVector, ReviewVector,
    DisagreementVector, DisagreementRecord, PromptVersion,
)
from app.models.audit import AuditLog, PortalNotification

__all__ = [
    "Org", "Department", "User", "RoleEnum",
    "Case", "CaseVersion", "CasePage", "Attachment", "CaseStatusEnum", "PageTypeEnum",
    "Review", "ReviewTask", "ReviewTypeEnum", "TaskStatusEnum", "DecisionEnum",
    "Rubric", "RubricVector", "CaseVector", "ReviewVector",
    "DisagreementVector", "DisagreementRecord", "PromptVersion",
    "AuditLog", "PortalNotification",
]
