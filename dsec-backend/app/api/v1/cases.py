"""Cases router."""
from uuid import UUID
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import select

from app.core.dependencies import CurrentUser, DB, require_roles
from app.models.user import RoleEnum
from app.schemas.case import (
    CaseCreate, CaseUpdate, CaseOut, CasePageCreate, CasePageUpdate,
    CasePageOut, CaseVersionOut, AttachmentOut, AttachmentUploadRequest,
    PresignedUploadResponse, CaseSubmitRequest,
)
from app.schemas.common import APIResponse, PaginatedData
from app.services.case import CaseService, AttachmentService
from app.workers.ai_review_worker import run_ai_review

router = APIRouter(prefix="/cases", tags=["cases"])


# ── Case CRUD ──────────────────────────────────────────────────────────────

@router.get("", response_model=APIResponse)
async def list_cases(
    current_user: CurrentUser,
    db: DB,
    status: str | None = Query(None),
    industry: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    svc = CaseService(db)
    cases, total = await svc.list_cases(
        current_user, status=status, industry=industry, page=page, page_size=page_size
    )
    return APIResponse(data=PaginatedData(
        items=[CaseOut.model_validate(c) for c in cases],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    ))


@router.post("", response_model=APIResponse)
async def create_case(
    payload: CaseCreate,
    current_user: CurrentUser,
    db: DB,
):
    svc = CaseService(db)
    case = await svc.create_case(payload, current_user)
    return APIResponse(data=CaseOut.model_validate(case))


@router.get("/{case_id}", response_model=APIResponse)
async def get_case(case_id: UUID, current_user: CurrentUser, db: DB):
    svc = CaseService(db)
    case = await svc.get_or_404(case_id, current_user)
    return APIResponse(data=CaseOut.model_validate(case))


@router.patch("/{case_id}", response_model=APIResponse)
async def update_case(
    case_id: UUID, payload: CaseUpdate, current_user: CurrentUser, db: DB
):
    svc = CaseService(db)
    case = await svc.update_case(case_id, payload, current_user)
    return APIResponse(data=CaseOut.model_validate(case))


@router.delete("/{case_id}", response_model=APIResponse)
async def delete_case(case_id: UUID, current_user: CurrentUser, db: DB):
    svc = CaseService(db)
    await svc.delete_case(case_id, current_user)
    return APIResponse(data={"deleted": str(case_id)})


# ── Submit / Withdraw ───────────────────────────────────────────────────────

@router.post("/{case_id}/submit", response_model=APIResponse)
async def submit_case(
    case_id: UUID,
    payload: CaseSubmitRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    db: DB,
):
    svc = CaseService(db)
    case = await svc.submit_case(case_id, payload, current_user)
    # Trigger AI review asynchronously
    background_tasks.add_task(run_ai_review, case_id)
    return APIResponse(data=CaseOut.model_validate(case))


@router.post("/{case_id}/withdraw", response_model=APIResponse)
async def withdraw_case(case_id: UUID, current_user: CurrentUser, db: DB):
    svc = CaseService(db)
    case = await svc.withdraw_case(case_id, current_user)
    return APIResponse(data=CaseOut.model_validate(case))


# ── Versions ────────────────────────────────────────────────────────────────

@router.get("/{case_id}/versions", response_model=APIResponse)
async def list_versions(case_id: UUID, current_user: CurrentUser, db: DB):
    from app.models.case import CaseVersion
    svc = CaseService(db)
    await svc.get_or_404(case_id, current_user)
    result = await db.execute(
        select(CaseVersion)
        .where(CaseVersion.case_id == case_id)
        .order_by(CaseVersion.version_number)
    )
    versions = result.scalars().all()
    return APIResponse(data=[CaseVersionOut.model_validate(v) for v in versions])


# ── Pages ───────────────────────────────────────────────────────────────────

@router.get("/{case_id}/pages", response_model=APIResponse)
async def list_pages(case_id: UUID, current_user: CurrentUser, db: DB):
    svc = CaseService(db)
    pages = await svc.get_pages(case_id, current_user)
    return APIResponse(data=[CasePageOut.model_validate(p) for p in pages])


@router.post("/{case_id}/pages", response_model=APIResponse)
async def add_page(
    case_id: UUID, payload: CasePageCreate, current_user: CurrentUser, db: DB
):
    svc = CaseService(db)
    page = await svc.add_page(case_id, payload, current_user)
    return APIResponse(data=CasePageOut.model_validate(page))


@router.put("/{case_id}/pages/{page_id}", response_model=APIResponse)
async def update_page(
    case_id: UUID,
    page_id: UUID,
    payload: CasePageUpdate,
    current_user: CurrentUser,
    db: DB,
):
    svc = CaseService(db)
    page = await svc.update_page(case_id, page_id, payload, current_user)
    return APIResponse(data=CasePageOut.model_validate(page))


@router.delete("/{case_id}/pages/{page_id}", response_model=APIResponse)
async def delete_page(
    case_id: UUID, page_id: UUID, current_user: CurrentUser, db: DB
):
    svc = CaseService(db)
    await svc.delete_page(case_id, page_id, current_user)
    return APIResponse(data={"deleted": str(page_id)})


# ── Attachments ──────────────────────────────────────────────────────────────

@router.post("/{case_id}/attachments", response_model=APIResponse)
async def create_attachment_upload_url(
    case_id: UUID,
    payload: AttachmentUploadRequest,
    current_user: CurrentUser,
    db: DB,
):
    svc = AttachmentService(db)
    attachment, presigned_url = await svc.create_upload_url(case_id, payload, current_user)
    return APIResponse(data=PresignedUploadResponse(
        attachment_id=attachment.id,
        upload_url=presigned_url,
        s3_key=attachment.s3_key,
        expires_in=900,
    ))


@router.get("/{case_id}/attachments/{attachment_id}/download", response_model=APIResponse)
async def get_download_url(
    case_id: UUID, attachment_id: UUID, current_user: CurrentUser, db: DB
):
    svc = AttachmentService(db)
    url = await svc.get_download_url(case_id, attachment_id, current_user)
    return APIResponse(data={"download_url": url, "expires_in": 900})


@router.delete("/{case_id}/attachments/{attachment_id}", response_model=APIResponse)
async def delete_attachment(
    case_id: UUID, attachment_id: UUID, current_user: CurrentUser, db: DB
):
    svc = AttachmentService(db)
    await svc.delete_attachment(case_id, attachment_id, current_user)
    return APIResponse(data={"deleted": str(attachment_id)})
