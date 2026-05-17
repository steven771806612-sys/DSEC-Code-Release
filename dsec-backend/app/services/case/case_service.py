"""Case domain service — business logic + state machine."""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    NotFoundError, ForbiddenError, ConflictError, InvalidTransitionError
)
from app.models.case import Case, CaseVersion, CasePage, Attachment, CaseStatusEnum
from app.models.user import User, RoleEnum
from app.schemas.case import (
    CaseCreate, CaseUpdate, CasePageCreate, CasePageUpdate,
    CaseSubmitRequest,
)

# ── State Machine ────────────────────────────────────────────────────────────

TRANSITIONS: dict[CaseStatusEnum, dict[str, CaseStatusEnum]] = {
    CaseStatusEnum.DRAFT: {
        "submit": CaseStatusEnum.SUBMITTED,
    },
    CaseStatusEnum.SUBMITTED: {
        "ai_complete": CaseStatusEnum.AI_REVIEWED,
        "ai_fail": CaseStatusEnum.DRAFT,
        "agent_withdraw": CaseStatusEnum.DRAFT,
    },
    CaseStatusEnum.AI_REVIEWED: {
        "platform_complete": CaseStatusEnum.PLATFORM_REVIEWED,
    },
    CaseStatusEnum.PLATFORM_REVIEWED: {
        "platform_reject": CaseStatusEnum.DRAFT,
        "dji_complete": CaseStatusEnum.DJI_REVIEWED,
    },
    CaseStatusEnum.DJI_REVIEWED: {
        "approve": CaseStatusEnum.APPROVED,
        "reject": CaseStatusEnum.REJECTED,
    },
}

EVENT_ACTOR_ROLES: dict[str, list[RoleEnum]] = {
    "submit": [RoleEnum.AGENT, RoleEnum.ADMIN],
    "agent_withdraw": [RoleEnum.AGENT, RoleEnum.ADMIN],
    "ai_complete": [],  # system only
    "ai_fail": [],
    "platform_complete": [RoleEnum.PLATFORM_REVIEWER, RoleEnum.ADMIN],
    "platform_reject": [RoleEnum.PLATFORM_REVIEWER, RoleEnum.ADMIN],
    "dji_complete": [RoleEnum.DJI_SE, RoleEnum.ADMIN],
    "approve": [RoleEnum.DJI_SE, RoleEnum.ADMIN],
    "reject": [RoleEnum.DJI_SE, RoleEnum.ADMIN],
}


def apply_transition(
    case: Case,
    event: str,
    actor: Optional[User] = None,
) -> CaseStatusEnum:
    """Apply a state transition and return the new status.
    Raises InvalidTransitionError if not allowed.
    """
    allowed = TRANSITIONS.get(case.status, {})
    if event not in allowed:
        raise InvalidTransitionError(case.status.value, event)

    if actor is not None:
        allowed_roles = EVENT_ACTOR_ROLES.get(event, [])
        if allowed_roles and actor.role not in allowed_roles:
            raise ForbiddenError(
                f"Role '{actor.role}' cannot apply event '{event}'"
            )

    return allowed[event]


# ── Case CRUD Service ─────────────────────────────────────────────────────────

class CaseService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_404(self, case_id: UUID, actor: User) -> Case:
        result = await self.db.execute(
            select(Case).where(Case.id == case_id)
        )
        case = result.scalar_one_or_none()
        if not case:
            raise NotFoundError("Case", str(case_id))
        self._check_read_access(case, actor)
        return case

    def _check_read_access(self, case: Case, actor: User) -> None:
        if actor.role in (RoleEnum.DJI_SE, RoleEnum.ADMIN):
            return
        if actor.role == RoleEnum.PLATFORM_REVIEWER:
            return
        # Agent: only own org
        if case.org_id != actor.org_id:
            raise ForbiddenError("You do not have access to this case")

    async def list_cases(
        self,
        actor: User,
        status: Optional[str] = None,
        industry: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Case], int]:
        q = select(Case)

        # Org isolation
        if actor.role == RoleEnum.AGENT:
            q = q.where(Case.org_id == actor.org_id)

        if status:
            q = q.where(Case.status == status)
        if industry:
            q = q.where(Case.industry == industry)

        total_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(total_q)).scalar_one()

        q = q.order_by(Case.updated_at.desc())
        q = q.offset((page - 1) * page_size).limit(page_size)
        cases = (await self.db.execute(q)).scalars().all()
        return list(cases), total

    async def create_case(self, payload: CaseCreate, actor: User) -> Case:
        case = Case(
            org_id=actor.org_id,
            created_by=actor.id,
            title=payload.title,
            industry=payload.industry,
            region=payload.region,
            tags=payload.tags,
            status=CaseStatusEnum.DRAFT,
        )
        self.db.add(case)
        await self.db.flush()
        return case

    async def update_case(
        self, case_id: UUID, payload: CaseUpdate, actor: User
    ) -> Case:
        case = await self.get_or_404(case_id, actor)
        if case.status != CaseStatusEnum.DRAFT:
            raise ConflictError("Only DRAFT cases can be edited")
        if actor.role == RoleEnum.AGENT and case.created_by != actor.id:
            raise ForbiddenError("You can only edit your own cases")

        update_data = payload.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(case, field, value)
        return case

    async def delete_case(self, case_id: UUID, actor: User) -> None:
        case = await self.get_or_404(case_id, actor)
        if case.status != CaseStatusEnum.DRAFT:
            raise ConflictError("Only DRAFT cases can be deleted")
        if actor.role == RoleEnum.AGENT and case.created_by != actor.id:
            raise ForbiddenError("You can only delete your own cases")
        await self.db.delete(case)

    async def submit_case(
        self, case_id: UUID, payload: CaseSubmitRequest, actor: User
    ) -> Case:
        case = await self.get_or_404(case_id, actor)

        # Validate: must have at least one page
        page_count_q = select(func.count()).where(
            CasePage.case_id == case_id
        )
        page_count = (await self.db.execute(page_count_q)).scalar_one()
        if page_count == 0:
            raise ConflictError("Cannot submit: case has no pages")

        new_status = apply_transition(case, "submit", actor)

        # Create a new CaseVersion snapshot
        version_result = await self.db.execute(
            select(func.count()).where(CaseVersion.case_id == case_id)
        )
        version_count = version_result.scalar_one()

        version = CaseVersion(
            case_id=case.id,
            version_number=version_count + 1,
            submitted_by=actor.id,
            change_summary=payload.change_summary,
            is_current=True,
        )
        self.db.add(version)
        await self.db.flush()

        # Deactivate previous versions
        prev_versions_q = select(CaseVersion).where(
            CaseVersion.case_id == case_id,
            CaseVersion.id != version.id,
        )
        prev_versions = (await self.db.execute(prev_versions_q)).scalars().all()
        for v in prev_versions:
            v.is_current = False

        case.status = new_status
        case.current_version_id = version.id
        case.submitted_at = datetime.now(timezone.utc)
        return case

    async def withdraw_case(self, case_id: UUID, actor: User) -> Case:
        case = await self.get_or_404(case_id, actor)
        if case.status != CaseStatusEnum.SUBMITTED:
            raise ConflictError("Only SUBMITTED cases can be withdrawn")
        if actor.role == RoleEnum.AGENT and case.created_by != actor.id:
            raise ForbiddenError("You can only withdraw your own cases")

        # 5-minute window
        if case.submitted_at:
            elapsed = datetime.now(timezone.utc) - case.submitted_at.replace(
                tzinfo=timezone.utc
            )
            if elapsed > timedelta(minutes=settings.CASE_WITHDRAW_WINDOW_MINUTES):
                raise ConflictError(
                    f"Withdraw window ({settings.CASE_WITHDRAW_WINDOW_MINUTES} min) has passed"
                )

        new_status = apply_transition(case, "agent_withdraw", actor)
        case.status = new_status
        return case

    async def system_transition(
        self, case_id: UUID, event: str
    ) -> Case:
        """System-level transition (no actor RBAC check)."""
        result = await self.db.execute(select(Case).where(Case.id == case_id))
        case = result.scalar_one_or_none()
        if not case:
            raise NotFoundError("Case", str(case_id))
        new_status = apply_transition(case, event)
        case.status = new_status
        if new_status in (CaseStatusEnum.APPROVED, CaseStatusEnum.REJECTED):
            case.closed_at = datetime.now(timezone.utc)
        return case

    # ── Pages ─────────────────────────────────────────────────────────────────

    async def add_page(
        self, case_id: UUID, payload: CasePageCreate, actor: User
    ) -> CasePage:
        case = await self.get_or_404(case_id, actor)
        if case.status != CaseStatusEnum.DRAFT:
            raise ConflictError("Pages can only be added to DRAFT cases")

        word_count = len((payload.content_text or "").split())
        page = CasePage(
            case_id=case_id,
            case_version_id=case.current_version_id or uuid.uuid4(),
            page_number=payload.page_number,
            page_type=payload.page_type,
            title=payload.title,
            content_text=payload.content_text,
            content_html=payload.content_html,
            word_count=word_count,
            has_images=payload.has_images,
        )
        self.db.add(page)
        await self.db.flush()
        return page

    async def update_page(
        self, case_id: UUID, page_id: UUID, payload: CasePageUpdate, actor: User
    ) -> CasePage:
        case = await self.get_or_404(case_id, actor)
        if case.status != CaseStatusEnum.DRAFT:
            raise ConflictError("Pages can only be edited in DRAFT cases")

        result = await self.db.execute(
            select(CasePage).where(
                CasePage.id == page_id, CasePage.case_id == case_id
            )
        )
        page = result.scalar_one_or_none()
        if not page:
            raise NotFoundError("CasePage", str(page_id))

        update_data = payload.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(page, field, value)
        if "content_text" in update_data:
            page.word_count = len((page.content_text or "").split())
        return page

    async def delete_page(self, case_id: UUID, page_id: UUID, actor: User) -> None:
        case = await self.get_or_404(case_id, actor)
        if case.status != CaseStatusEnum.DRAFT:
            raise ConflictError("Pages can only be deleted in DRAFT cases")
        result = await self.db.execute(
            select(CasePage).where(
                CasePage.id == page_id, CasePage.case_id == case_id
            )
        )
        page = result.scalar_one_or_none()
        if not page:
            raise NotFoundError("CasePage", str(page_id))
        await self.db.delete(page)

    async def get_pages(self, case_id: UUID, actor: User) -> list[CasePage]:
        await self.get_or_404(case_id, actor)
        result = await self.db.execute(
            select(CasePage)
            .where(CasePage.case_id == case_id)
            .order_by(CasePage.page_number)
        )
        return list(result.scalars().all())
