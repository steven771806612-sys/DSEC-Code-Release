"""Reviews router."""
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Query

from app.core.dependencies import CurrentUser, DB, AdminUser
from app.schemas.review import (
    ReviewOut, ReviewTaskOut, PlatformReviewSubmit, DJIReviewSubmit,
    OverrideRequest, AIReviewTrigger,
)
from app.schemas.common import APIResponse, PaginatedData
from app.services.review import ReviewService, DisagreementService
from app.services.case import CaseService
from app.workers.ai_review_worker import run_ai_review
from app.workers.knowledge_worker import run_knowledge_ingest
from app.models.case import CaseStatusEnum

router = APIRouter(tags=["reviews"])


# ── Task List ────────────────────────────────────────────────────────────────

@router.get("/reviews/tasks", response_model=APIResponse)
async def my_tasks(
    current_user: CurrentUser,
    db: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    svc = ReviewService(db)
    tasks, total = await svc.get_my_tasks(current_user, page=page, page_size=page_size)
    return APIResponse(data=PaginatedData(
        items=[ReviewTaskOut.model_validate(t) for t in tasks],
        total=total, page=page, page_size=page_size,
        has_next=(page * page_size) < total,
    ))


# ── AI Review ────────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/reviews/ai", response_model=APIResponse)
async def get_ai_review(case_id: UUID, current_user: CurrentUser, db: DB):
    svc = ReviewService(db)
    review = await svc.get_ai_review(case_id)
    if not review:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("AI Review", str(case_id))
    return APIResponse(data=ReviewOut.model_validate(review))


@router.post("/cases/{case_id}/reviews/ai/trigger", response_model=APIResponse)
async def trigger_ai_review(
    case_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: AdminUser,
    db: DB,
):
    background_tasks.add_task(run_ai_review, case_id)
    return APIResponse(data={"triggered": True, "case_id": str(case_id)})


# ── Platform Review ───────────────────────────────────────────────────────────

@router.post("/cases/{case_id}/reviews/platform", response_model=APIResponse)
async def submit_platform_review(
    case_id: UUID,
    payload: PlatformReviewSubmit,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    db: DB,
):
    svc = ReviewService(db)
    review = await svc.submit_platform_review(case_id, payload, current_user)

    # Transition case state
    case_svc = CaseService(db)
    if payload.decision == "reject":
        case = await case_svc.system_transition(case_id, "platform_reject")
    else:
        case = await case_svc.system_transition(case_id, "platform_complete")
        # Assign DJI review task
        dji_task = await svc.create_task(case, review_type=svc._import_review_type("dji"))

    return APIResponse(data=ReviewOut.model_validate(review))


# ── DJI Review ────────────────────────────────────────────────────────────────

@router.post("/cases/{case_id}/reviews/dji", response_model=APIResponse)
async def submit_dji_review(
    case_id: UUID,
    payload: DJIReviewSubmit,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    db: DB,
):
    svc = ReviewService(db)
    review = await svc.submit_dji_review(case_id, payload, current_user)

    # Transition case to DJI_REVIEWED then APPROVED/REJECTED
    case_svc = CaseService(db)
    await case_svc.system_transition(case_id, "dji_complete")

    if payload.decision == "approve":
        case = await case_svc.system_transition(case_id, "approve")
        # Trigger knowledge ingest
        background_tasks.add_task(run_knowledge_ingest, case_id)
    else:
        case = await case_svc.system_transition(case_id, "reject")

    # Disagreement detection
    ai_review = await svc.get_ai_review(case_id)
    if ai_review and review:
        disagreement_svc = DisagreementService(db)
        await disagreement_svc.detect_and_record(case_id, ai_review, review)

    return APIResponse(data=ReviewOut.model_validate(review))


# ── All Reviews ───────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/reviews", response_model=APIResponse)
async def get_case_reviews(case_id: UUID, current_user: CurrentUser, db: DB):
    svc = ReviewService(db)
    reviews = await svc.get_case_reviews(case_id)
    return APIResponse(data=[ReviewOut.model_validate(r) for r in reviews])


# ── Override ─────────────────────────────────────────────────────────────────

@router.post("/reviews/{review_id}/override", response_model=APIResponse)
async def override_review(
    review_id: UUID, payload: OverrideRequest, current_user: CurrentUser, db: DB
):
    svc = ReviewService(db)
    review = await svc.override_review(review_id, payload, current_user)
    return APIResponse(data=ReviewOut.model_validate(review))
