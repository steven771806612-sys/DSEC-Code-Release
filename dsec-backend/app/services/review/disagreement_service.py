"""Disagreement detection service."""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.rag import DisagreementRecord
from app.models.review import Review, ReviewTypeEnum


class DisagreementService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def detect_and_record(
        self,
        case_id: UUID,
        ai_review: Review,
        human_review: Review,
        dimension: Optional[str] = None,
    ) -> Optional[DisagreementRecord]:
        """
        Compare AI review vs human review. If gap exceeds threshold,
        create a DisagreementRecord.
        """
        if ai_review.overall_score is None or human_review.overall_score is None:
            return None

        score_gap = abs(ai_review.overall_score - human_review.overall_score)

        # Determine severity
        if score_gap >= settings.DISAGREEMENT_CRITICAL_THRESHOLD:
            severity = "critical"
        elif score_gap >= settings.DISAGREEMENT_MAJOR_THRESHOLD:
            severity = "major"
        elif score_gap > 0:
            severity = "minor"
        else:
            return None

        # Check decision flip
        disagreement_type = "score_gap"
        if (
            ai_review.decision is not None
            and human_review.decision is not None
            and ai_review.decision != human_review.decision
        ):
            disagreement_type = "decision_flip"

        record = DisagreementRecord(
            case_id=case_id,
            ai_review_id=ai_review.id,
            human_review_id=human_review.id,
            disagreement_type=disagreement_type,
            ai_score=ai_review.overall_score,
            human_score=human_review.overall_score,
            score_gap=score_gap,
            severity=severity,
            dimension=dimension,
            ai_reasoning=str(ai_review.raw_llm_output or ""),
            human_reasoning=human_review.override_reason or "",
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def mark_training_signal(self, disagreement_id: UUID) -> DisagreementRecord:
        result = await self.db.execute(
            select(DisagreementRecord).where(DisagreementRecord.id == disagreement_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("DisagreementRecord", str(disagreement_id))
        record.is_training_signal = True
        return record
