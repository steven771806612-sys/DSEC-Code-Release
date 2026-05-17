"""Knowledge ingestion background worker."""
from uuid import UUID
import structlog

from app.core.database import AsyncSessionLocal
from app.models.case import CasePage, Case
from app.models.review import Review, ReviewTypeEnum
from app.models.rag import DisagreementRecord
from app.services.rag.knowledge_ingest_service import KnowledgeIngestService
from sqlalchemy import select

log = structlog.get_logger()


async def run_knowledge_ingest(case_id: UUID) -> None:
    """Ingest approved case data into vector DB."""
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(Case).where(Case.id == case_id))
            case = result.scalar_one_or_none()
            if not case:
                return

            pages_result = await db.execute(
                select(CasePage).where(CasePage.case_id == case_id)
            )
            pages = list(pages_result.scalars().all())

            # Get final score from DJI review
            dji_review_result = await db.execute(
                select(Review).where(
                    Review.case_id == case_id,
                    Review.review_type == ReviewTypeEnum.DJI,
                ).order_by(Review.created_at.desc()).limit(1)
            )
            dji_review = dji_review_result.scalar_one_or_none()
            final_score = dji_review.overall_score if dji_review else 0.0

            ingest_svc = KnowledgeIngestService(db)
            count = await ingest_svc.ingest_approved_case(
                case_id=case_id,
                pages=pages,
                final_score=final_score or 0.0,
                industry=case.industry or "",
                region=case.region or "",
                rubric_version=case.rubric_version,
            )

            # Ingest DJI review opinion
            if dji_review:
                await ingest_svc.ingest_review(dji_review, case.industry or "")

            await db.commit()
            log.info("knowledge_ingest_complete", case_id=str(case_id), vectors=count)
        except Exception as exc:
            await db.rollback()
            log.error("knowledge_ingest_failed", case_id=str(case_id), error=str(exc))
