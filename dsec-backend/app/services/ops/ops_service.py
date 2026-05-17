"""Ops/Admin service — audit logging, prompt management, dashboard metrics."""
import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.rag import PromptVersion, Rubric, DisagreementRecord
from app.schemas.ops import DashboardMetrics


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        action: str,
        actor_id: Optional[UUID] = None,
        actor_role: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        old_value: Optional[dict] = None,
        new_value: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        result: str = "success",
        error_message: Optional[str] = None,
    ) -> AuditLog:
        log_entry = AuditLog(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            result=result,
            error_message=error_message,
        )
        self.db.add(log_entry)
        await self.db.flush()
        return log_entry

    async def list_logs(
        self,
        resource_type: Optional[str] = None,
        actor_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditLog], int]:
        q = select(AuditLog)
        if resource_type:
            q = q.where(AuditLog.resource_type == resource_type)
        if actor_id:
            q = q.where(AuditLog.actor_id == actor_id)

        total = (await self.db.execute(
            select(func.count()).select_from(q.subquery())
        )).scalar_one()

        logs = (await self.db.execute(
            q.order_by(AuditLog.timestamp.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )).scalars().all()

        return list(logs), total


class PromptService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_prompt(self, prompt_type: str) -> Optional[PromptVersion]:
        """Get the active (or canary) prompt for a given type."""
        import random

        # Check for canary
        canary_q = await self.db.execute(
            select(PromptVersion).where(
                PromptVersion.prompt_type == prompt_type,
                PromptVersion.is_canary.is_(True),
                PromptVersion.canary_percentage > 0,
            )
        )
        canary = canary_q.scalar_one_or_none()
        if canary and random.random() < canary.canary_percentage / 100:
            return canary

        # Return stable active version
        result = await self.db.execute(
            select(PromptVersion).where(
                PromptVersion.prompt_type == prompt_type,
                PromptVersion.is_active.is_(True),
                PromptVersion.is_canary.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def activate_prompt(self, prompt_id: UUID) -> PromptVersion:
        result = await self.db.execute(
            select(PromptVersion).where(PromptVersion.id == prompt_id)
        )
        prompt = result.scalar_one_or_none()
        if not prompt:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("PromptVersion", str(prompt_id))

        # Deactivate current active
        current_q = await self.db.execute(
            select(PromptVersion).where(
                PromptVersion.prompt_type == prompt.prompt_type,
                PromptVersion.is_active.is_(True),
            )
        )
        for p in current_q.scalars().all():
            p.is_active = False

        prompt.is_active = True
        prompt.activated_at = datetime.now(timezone.utc)
        return prompt

    async def rollback_prompt(self, prompt_type: str) -> Optional[PromptVersion]:
        """Activate the previous version."""
        result = await self.db.execute(
            select(PromptVersion)
            .where(PromptVersion.prompt_type == prompt_type)
            .order_by(PromptVersion.activated_at.desc().nullslast())
            .offset(1)
            .limit(1)
        )
        prev = result.scalar_one_or_none()
        if prev:
            return await self.activate_prompt(prev.id)
        return None


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_metrics(self) -> DashboardMetrics:
        from app.models.case import Case, CaseStatusEnum
        from app.models.review import Review, ReviewTypeEnum

        # Total cases
        total_cases = (await self.db.execute(
            select(func.count()).select_from(Case)
        )).scalar_one()

        # Cases by status
        status_counts = (await self.db.execute(
            select(Case.status, func.count())
            .group_by(Case.status)
        )).fetchall()
        cases_by_status = {row[0].value: row[1] for row in status_counts}

        # AI approval rate: cases AI said approve that ended up APPROVED
        total_ai_reviews = (await self.db.execute(
            select(func.count()).where(Review.review_type == ReviewTypeEnum.AI)
        )).scalar_one()

        approved_ai = (await self.db.execute(
            select(func.count())
            .select_from(Review)
            .join(Case, Review.case_id == Case.id)
            .where(
                Review.review_type == ReviewTypeEnum.AI,
                Case.status == CaseStatusEnum.APPROVED,
            )
        )).scalar_one()

        ai_approval_rate = (approved_ai / total_ai_reviews * 100) if total_ai_reviews > 0 else 0.0

        # Major disagreement rate
        total_disagreements = (await self.db.execute(
            select(func.count()).select_from(DisagreementRecord)
        )).scalar_one()
        major_disagreements = (await self.db.execute(
            select(func.count()).where(
                DisagreementRecord.severity.in_(["major", "critical"])
            )
        )).scalar_one()
        disagreement_rate = (major_disagreements / total_disagreements * 100) if total_disagreements > 0 else 0.0

        # Vector counts
        vector_counts = {}
        for table in ["rubric_vectors", "case_vectors", "review_vectors", "disagreement_vectors"]:
            count = (await self.db.execute(
                text(f"SELECT COUNT(*) FROM {table}")
            )).scalar_one()
            vector_counts[table] = count

        return DashboardMetrics(
            total_cases=total_cases,
            cases_by_status=cases_by_status,
            ai_approval_rate=round(ai_approval_rate, 2),
            major_disagreement_rate=round(disagreement_rate, 2),
            avg_review_latency_seconds=0.0,  # TODO: calculate from audit logs
            total_vectors=vector_counts,
        )
