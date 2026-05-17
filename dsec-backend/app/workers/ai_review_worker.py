"""AI Review background worker.

Triggered after a case is submitted. Runs the full RAG pipeline
page-by-page, then transitions the case to AI_REVIEWED.
"""
import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.case import Case, CasePage, CaseStatusEnum
from app.models.review import Review, ReviewTask, ReviewTypeEnum, TaskStatusEnum, DecisionEnum
from app.services.rag.retrieval_service import RetrievalService
from app.services.rag.evaluation_service import EvaluationService, AIReviewOutput
from app.services.notification.notification_service import notification_service
from app.core.config import settings

log = structlog.get_logger()


async def run_ai_review(case_id: UUID) -> None:
    """
    Entry point — called as a FastAPI BackgroundTask after case submission.
    Opens its own DB session for the full async operation.
    """
    async with AsyncSessionLocal() as db:
        try:
            await _execute_review(db, case_id)
            await db.commit()
        except Exception as exc:
            await db.rollback()
            log.error("ai_review_failed", case_id=str(case_id), error=str(exc))
            # Transition case back to DRAFT with error flag
            async with AsyncSessionLocal() as err_db:
                try:
                    result = await err_db.execute(
                        select(Case).where(Case.id == case_id)
                    )
                    case = result.scalar_one_or_none()
                    if case:
                        case.status = CaseStatusEnum.DRAFT
                    await err_db.commit()
                except Exception:
                    pass


async def _execute_review(db: AsyncSession, case_id: UUID) -> None:
    log.info("ai_review_started", case_id=str(case_id))

    # Load case
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()
    if not case or case.status != CaseStatusEnum.SUBMITTED:
        log.warning("ai_review_skip", case_id=str(case_id), reason="case not in SUBMITTED state")
        return

    # Create AI review task
    task = ReviewTask(
        case_id=case_id,
        review_type=ReviewTypeEnum.AI,
        status=TaskStatusEnum.IN_PROGRESS,
        started_at=datetime.now(timezone.utc),
    )
    db.add(task)
    await db.flush()

    # Load pages
    pages_result = await db.execute(
        select(CasePage)
        .where(CasePage.case_id == case_id)
        .order_by(CasePage.page_number)
    )
    pages = list(pages_result.scalars().all())

    if not pages:
        log.warning("ai_review_no_pages", case_id=str(case_id))
        task.status = TaskStatusEnum.SKIPPED
        case.status = CaseStatusEnum.AI_REVIEWED
        return

    # RAG evaluation per page
    retrieval_svc = RetrievalService(db)
    evaluator = EvaluationService()

    page_results: list[AIReviewOutput] = []
    all_issues: list[dict] = []
    all_recommendations: list[str] = []

    for page in pages:
        if not page.content_text:
            continue

        chunks = await retrieval_svc.retrieve_for_page(
            content_text=page.content_text,
            industry=case.industry,
            region=case.region,
            rubric_version=case.rubric_version,
        )

        page_result = await evaluator.evaluate_page(
            page_id=page.id,
            page_type=page.page_type.value if page.page_type else "overview",
            content_text=page.content_text,
            retrieved_chunks=chunks,
            industry=case.industry or "",
            region=case.region or "",
            rubric_version=case.rubric_version,
        )
        page_results.append(page_result)
        all_issues.extend(page_result.critical_issues)
        all_recommendations.append(page_result.reasoning_summary)

    # Aggregate scores
    scored = [r for r in page_results if r.overall_score is not None]
    overall_score = sum(r.overall_score for r in scored) / len(scored) if scored else 0.0
    avg_confidence = sum(r.confidence for r in page_results) / len(page_results) if page_results else 0.0

    # Determine preliminary decision
    decision = DecisionEnum.REVISE
    if overall_score >= 75 and avg_confidence >= settings.RAG_CONFIDENCE_THRESHOLD:
        decision = DecisionEnum.APPROVE

    # Write review record
    review = Review(
        case_id=case_id,
        case_version_id=case.current_version_id,
        review_task_id=task.id,
        reviewer_id=None,  # AI
        review_type=ReviewTypeEnum.AI,
        overall_score=round(overall_score, 2),
        dimension_scores={
            f"page_{r.page_id}": {
                "score": r.overall_score,
                "dimensions": [d.model_dump() for d in r.dimension_scores],
            }
            for r in page_results
        },
        issues=all_issues[:20],
        recommendations=all_recommendations[:10],
        decision=decision,
        confidence=round(avg_confidence, 3),
        raw_llm_output={"pages": [r.model_dump() for r in page_results]},
    )
    db.add(review)

    task.status = TaskStatusEnum.COMPLETED
    task.completed_at = datetime.now(timezone.utc)

    # Transition case
    case.status = CaseStatusEnum.AI_REVIEWED

    await db.flush()

    log.info(
        "ai_review_completed",
        case_id=str(case_id),
        overall_score=overall_score,
        confidence=avg_confidence,
        pages_reviewed=len(page_results),
    )
