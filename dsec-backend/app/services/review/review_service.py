"""Review task service + assignment engine."""
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ForbiddenError, ConflictError
from app.models.case import Case, CaseVersion, CaseStatusEnum
from app.models.review import Review, ReviewTask, ReviewTypeEnum, TaskStatusEnum, DecisionEnum
from app.models.user import User, RoleEnum
from app.schemas.review import PlatformReviewSubmit, DJIReviewSubmit, OverrideRequest


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Assignment Engine ─────────────────────────────────────────────────────

    async def assign_reviewer(
        self, case: Case, review_type: ReviewTypeEnum
    ) -> Optional[UUID]:
        """Route review to appropriate user. Returns user_id or None (AI)."""
        if review_type == ReviewTypeEnum.AI:
            return None

        if review_type == ReviewTypeEnum.PLATFORM:
            return await self._find_least_loaded_reviewer(
                role=RoleEnum.PLATFORM_REVIEWER,
                region=case.region,
            )

        if review_type == ReviewTypeEnum.DJI:
            return await self._find_least_loaded_reviewer(
                role=RoleEnum.DJI_SE,
                region=case.region,
            )
        return None

    async def _find_least_loaded_reviewer(
        self, role: RoleEnum, region: Optional[str] = None
    ) -> Optional[UUID]:
        """Find active reviewer with the lowest active task count."""
        # Subquery: count active tasks per user
        active_tasks = (
            select(
                ReviewTask.assigned_to,
                func.count().label("task_count"),
            )
            .where(ReviewTask.status.in_([TaskStatusEnum.PENDING, TaskStatusEnum.IN_PROGRESS]))
            .group_by(ReviewTask.assigned_to)
            .subquery()
        )

        q = (
            select(User)
            .outerjoin(active_tasks, User.id == active_tasks.c.assigned_to)
            .where(User.role == role, User.is_active.is_(True))
            .order_by(func.coalesce(active_tasks.c.task_count, 0).asc())
            .limit(1)
        )

        result = await self.db.execute(q)
        user = result.scalar_one_or_none()
        return user.id if user else None

    # ── Task Lifecycle ────────────────────────────────────────────────────────

    async def create_task(
        self,
        case: Case,
        review_type: ReviewTypeEnum,
        priority: int = 3,
    ) -> ReviewTask:
        assigned_to = await self.assign_reviewer(case, review_type)

        sla_hours = (
            settings.SLA_PLATFORM_REVIEW_HOURS
            if review_type == ReviewTypeEnum.PLATFORM
            else settings.SLA_DJI_REVIEW_HOURS
        )
        due_at = datetime.now(timezone.utc) + timedelta(hours=sla_hours)

        task = ReviewTask(
            case_id=case.id,
            review_type=review_type,
            assigned_to=assigned_to,
            status=TaskStatusEnum.PENDING,
            priority=priority,
            due_at=due_at if review_type != ReviewTypeEnum.AI else None,
        )
        self.db.add(task)
        await self.db.flush()
        return task

    async def get_my_tasks(
        self, actor: User, page: int = 1, page_size: int = 20
    ) -> tuple[list[ReviewTask], int]:
        q = select(ReviewTask).where(
            ReviewTask.assigned_to == actor.id,
            ReviewTask.status.in_([TaskStatusEnum.PENDING, TaskStatusEnum.IN_PROGRESS]),
        )
        total = (await self.db.execute(
            select(func.count()).select_from(q.subquery())
        )).scalar_one()

        tasks = (
            await self.db.execute(
                q.order_by(ReviewTask.priority.desc(), ReviewTask.due_at.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()

        return list(tasks), total

    # ── Review Submission ─────────────────────────────────────────────────────

    async def submit_platform_review(
        self,
        case_id: UUID,
        payload: PlatformReviewSubmit,
        actor: User,
    ) -> Review:
        if actor.role not in (RoleEnum.PLATFORM_REVIEWER, RoleEnum.ADMIN):
            raise ForbiddenError("Only platform reviewers can submit platform reviews")

        case = await self._get_case_or_404(case_id)
        if case.status != CaseStatusEnum.AI_REVIEWED:
            raise ConflictError(
                f"Platform review requires AI_REVIEWED status, got {case.status}"
            )

        task = await self._get_or_create_active_task(
            case_id, ReviewTypeEnum.PLATFORM
        )
        task.status = TaskStatusEnum.COMPLETED
        task.completed_at = datetime.now(timezone.utc)

        review = Review(
            case_id=case_id,
            case_version_id=case.current_version_id,
            review_task_id=task.id,
            reviewer_id=actor.id,
            review_type=ReviewTypeEnum.PLATFORM,
            overall_score=payload.overall_score,
            dimension_scores=payload.dimension_scores,
            issues=payload.issues,
            recommendations=payload.recommendations,
            decision=DecisionEnum(payload.decision),
            is_override=payload.is_override,
            override_reason=payload.override_reason,
        )
        self.db.add(review)
        await self.db.flush()
        return review

    async def submit_dji_review(
        self,
        case_id: UUID,
        payload: DJIReviewSubmit,
        actor: User,
    ) -> Review:
        if actor.role not in (RoleEnum.DJI_SE, RoleEnum.ADMIN):
            raise ForbiddenError("Only DJI SE can submit DJI reviews")

        case = await self._get_case_or_404(case_id)
        if case.status != CaseStatusEnum.PLATFORM_REVIEWED:
            raise ConflictError(
                f"DJI review requires PLATFORM_REVIEWED status, got {case.status}"
            )

        task = await self._get_or_create_active_task(
            case_id, ReviewTypeEnum.DJI
        )
        task.status = TaskStatusEnum.COMPLETED
        task.completed_at = datetime.now(timezone.utc)

        review = Review(
            case_id=case_id,
            case_version_id=case.current_version_id,
            review_task_id=task.id,
            reviewer_id=actor.id,
            review_type=ReviewTypeEnum.DJI,
            overall_score=payload.overall_score,
            dimension_scores=payload.dimension_scores,
            issues=payload.issues,
            recommendations=payload.recommendations,
            decision=DecisionEnum(payload.decision),
            override_reason=payload.override_reason,
        )
        self.db.add(review)
        await self.db.flush()
        return review

    async def override_review(
        self, review_id: UUID, payload: OverrideRequest, actor: User
    ) -> Review:
        result = await self.db.execute(
            select(Review).where(Review.id == review_id)
        )
        review = result.scalar_one_or_none()
        if not review:
            raise NotFoundError("Review", str(review_id))

        # Only higher-authority roles can override
        if review.review_type == ReviewTypeEnum.DJI:
            raise ForbiddenError("DJI reviews cannot be overridden")

        if payload.overall_score is not None:
            review.overall_score = payload.overall_score
        if payload.decision is not None:
            review.decision = DecisionEnum(payload.decision)
        review.is_override = True
        review.override_reason = payload.override_reason
        review.updated_at = datetime.now(timezone.utc)
        return review

    async def get_case_reviews(self, case_id: UUID) -> list[Review]:
        result = await self.db.execute(
            select(Review)
            .where(Review.case_id == case_id)
            .order_by(Review.created_at)
        )
        return list(result.scalars().all())

    async def get_ai_review(self, case_id: UUID) -> Optional[Review]:
        result = await self.db.execute(
            select(Review)
            .where(
                Review.case_id == case_id,
                Review.review_type == ReviewTypeEnum.AI,
            )
            .order_by(Review.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get_case_or_404(self, case_id: UUID) -> Case:
        result = await self.db.execute(select(Case).where(Case.id == case_id))
        case = result.scalar_one_or_none()
        if not case:
            raise NotFoundError("Case", str(case_id))
        return case

    async def _get_or_create_active_task(
        self, case_id: UUID, review_type: ReviewTypeEnum
    ) -> ReviewTask:
        result = await self.db.execute(
            select(ReviewTask).where(
                ReviewTask.case_id == case_id,
                ReviewTask.review_type == review_type,
                ReviewTask.status.in_([
                    TaskStatusEnum.PENDING, TaskStatusEnum.IN_PROGRESS
                ]),
            ).order_by(ReviewTask.created_at.desc()).limit(1)
        )
        task = result.scalar_one_or_none()
        if not task:
            # Create one on the fly
            case = await self._get_case_or_404(case_id)
            task = ReviewTask(
                case_id=case_id,
                review_type=review_type,
                status=TaskStatusEnum.IN_PROGRESS,
                started_at=datetime.now(timezone.utc),
            )
            self.db.add(task)
            await self.db.flush()
        return task
