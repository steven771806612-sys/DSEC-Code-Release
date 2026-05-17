"""Ops router — dashboard, prompts, audit logs, vector stats."""
from uuid import UUID
from fastapi import APIRouter, Query
from sqlalchemy import select, text

from app.core.dependencies import DB, AdminUser, DJIOrAdminUser
from app.models.rag import PromptVersion
from app.schemas.ops import (
    PromptVersionCreate, PromptVersionOut, CanaryConfig, DashboardMetrics
)
from app.schemas.common import APIResponse, PaginatedData
from app.services.ops import AuditService, PromptService, DashboardService

router = APIRouter(prefix="/ops", tags=["ops"])


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=APIResponse)
async def get_dashboard(
    current_user: DJIOrAdminUser,
    db: DB,
):
    svc = DashboardService(db)
    metrics = await svc.get_metrics()
    return APIResponse(data=metrics)


# ── Prompt Management ─────────────────────────────────────────────────────────

@router.get("/prompts", response_model=APIResponse)
async def list_prompts(
    current_user: AdminUser,
    db: DB,
    prompt_type: str | None = Query(None),
):
    q = select(PromptVersion)
    if prompt_type:
        q = q.where(PromptVersion.prompt_type == prompt_type)
    result = await db.execute(q.order_by(PromptVersion.created_at.desc()))
    prompts = result.scalars().all()
    return APIResponse(data=[PromptVersionOut.model_validate(p) for p in prompts])


@router.post("/prompts", response_model=APIResponse)
async def create_prompt(
    payload: PromptVersionCreate,
    current_user: AdminUser,
    db: DB,
):
    prompt = PromptVersion(
        prompt_type=payload.prompt_type,
        version=payload.version,
        content=payload.content,
        created_by=current_user.id,
    )
    db.add(prompt)
    await db.flush()
    return APIResponse(data=PromptVersionOut.model_validate(prompt))


@router.put("/prompts/{prompt_id}/activate", response_model=APIResponse)
async def activate_prompt(
    prompt_id: UUID,
    current_user: AdminUser,
    db: DB,
):
    svc = PromptService(db)
    prompt = await svc.activate_prompt(prompt_id)
    return APIResponse(data=PromptVersionOut.model_validate(prompt))


@router.put("/prompts/{prompt_id}/canary", response_model=APIResponse)
async def set_canary(
    prompt_id: UUID,
    payload: CanaryConfig,
    current_user: AdminUser,
    db: DB,
):
    result = await db.execute(select(PromptVersion).where(PromptVersion.id == prompt_id))
    prompt = result.scalar_one_or_none()
    if not prompt:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("PromptVersion", str(prompt_id))
    prompt.is_canary = True
    prompt.canary_percentage = payload.canary_percentage
    return APIResponse(data=PromptVersionOut.model_validate(prompt))


@router.post("/prompts/{prompt_id}/rollback", response_model=APIResponse)
async def rollback_prompt(
    prompt_id: UUID,
    current_user: AdminUser,
    db: DB,
):
    result = await db.execute(select(PromptVersion).where(PromptVersion.id == prompt_id))
    prompt = result.scalar_one_or_none()
    if not prompt:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("PromptVersion", str(prompt_id))
    svc = PromptService(db)
    prev = await svc.rollback_prompt(prompt.prompt_type)
    return APIResponse(data=PromptVersionOut.model_validate(prev) if prev else None)


# ── Audit Logs ────────────────────────────────────────────────────────────────

@router.get("/audit-logs", response_model=APIResponse)
async def list_audit_logs(
    current_user: AdminUser,
    db: DB,
    resource_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    svc = AuditService(db)
    logs, total = await svc.list_logs(resource_type=resource_type, page=page, page_size=page_size)
    return APIResponse(data=PaginatedData(
        items=[{"id": str(l.id), "action": l.action, "actor_role": l.actor_role,
                "resource_type": l.resource_type, "timestamp": l.timestamp.isoformat(),
                "result": l.result} for l in logs],
        total=total, page=page, page_size=page_size,
        has_next=(page * page_size) < total,
    ))


# ── Vector Stats ──────────────────────────────────────────────────────────────

@router.get("/vectors/stats", response_model=APIResponse)
async def vector_stats(
    current_user: DJIOrAdminUser,
    db: DB,
):
    stats = {}
    for table in ["rubric_vectors", "case_vectors", "review_vectors", "disagreement_vectors"]:
        count = (await db.execute(text(f"SELECT COUNT(*) FROM {table}"))).scalar_one()
        stats[table] = count
    return APIResponse(data=stats)


@router.post("/vectors/search", response_model=APIResponse)
async def debug_vector_search(
    payload: dict,
    current_user: AdminUser,
    db: DB,
):
    """Debug endpoint — raw vector search across any table."""
    from app.schemas.ops import VectorSearchRequest
    from app.api.v1.rag import search_knowledge
    return await search_knowledge(VectorSearchRequest(**payload), current_user, db)
