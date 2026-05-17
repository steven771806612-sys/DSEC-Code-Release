"""RAG management router."""
from uuid import UUID
from fastapi import APIRouter, Query
from sqlalchemy import select, text

from app.core.dependencies import DB, AdminUser, DJIOrAdminUser
from app.models.rag import Rubric, DisagreementRecord
from app.schemas.ops import (
    RubricCreate, RubricOut, DisagreementOut, VectorSearchRequest, VectorSearchResult
)
from app.schemas.common import APIResponse, PaginatedData
from app.services.rag.embedding_service import embed_text
from app.services.rag.knowledge_ingest_service import KnowledgeIngestService
from app.services.review.disagreement_service import DisagreementService

router = APIRouter(prefix="/rag", tags=["rag"])


# ── Knowledge Search ──────────────────────────────────────────────────────────

@router.post("/search", response_model=APIResponse)
async def search_knowledge(
    payload: VectorSearchRequest,
    current_user: DJIOrAdminUser,
    db: DB,
):
    embedding = await embed_text(payload.query)
    table = payload.collection

    filters = ["embedding IS NOT NULL"]
    if payload.industry:
        filters.append(f"industry = '{payload.industry}'")
    where = " AND ".join(filters)

    sql = text(f"""
        SELECT id, content,
               1 - (embedding <=> :embedding::vector) AS similarity
        FROM {table}
        WHERE {where}
        ORDER BY embedding <=> :embedding::vector
        LIMIT :top_k
    """)
    result = await db.execute(sql, {"embedding": str(embedding), "top_k": payload.top_k})
    rows = result.fetchall()

    return APIResponse(data=[
        VectorSearchResult(id=row.id, content=row.content, similarity=float(row.similarity))
        for row in rows
    ])


# ── Rubric Management ─────────────────────────────────────────────────────────

@router.post("/rubrics", response_model=APIResponse)
async def create_rubric(
    payload: RubricCreate,
    current_user: AdminUser,
    db: DB,
):
    rubric = Rubric(
        title=payload.title,
        version=payload.version,
        content=payload.content,
        dimensions=payload.dimensions,
        created_by=current_user.id,
    )
    db.add(rubric)
    await db.flush()
    return APIResponse(data=RubricOut.model_validate(rubric))


@router.put("/rubrics/{rubric_id}/activate", response_model=APIResponse)
async def activate_rubric(
    rubric_id: UUID,
    current_user: AdminUser,
    db: DB,
):
    from datetime import datetime, timezone
    result = await db.execute(select(Rubric).where(Rubric.id == rubric_id))
    rubric = result.scalar_one_or_none()
    if not rubric:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Rubric", str(rubric_id))

    # Deactivate others of same version
    all_rubrics = (await db.execute(select(Rubric).where(Rubric.is_active.is_(True)))).scalars().all()
    for r in all_rubrics:
        r.is_active = False

    rubric.is_active = True
    rubric.activated_at = datetime.now(timezone.utc)
    return APIResponse(data=RubricOut.model_validate(rubric))


@router.post("/rubrics/{rubric_id}/reindex", response_model=APIResponse)
async def reindex_rubric(
    rubric_id: UUID,
    current_user: AdminUser,
    db: DB,
):
    """Re-embed rubric content into rubric_vectors."""
    result = await db.execute(select(Rubric).where(Rubric.id == rubric_id))
    rubric = result.scalar_one_or_none()
    if not rubric:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Rubric", str(rubric_id))

    ingest_svc = KnowledgeIngestService(db)
    if rubric.content:
        await ingest_svc.ingest_rubric_chunk(
            content=rubric.content,
            rubric_id=rubric_id,
            dimension="general",
            version=rubric.version,
        )

    # Embed each dimension
    count = 1
    for dim in rubric.dimensions or []:
        if isinstance(dim, dict) and dim.get("content"):
            await ingest_svc.ingest_rubric_chunk(
                content=dim["content"],
                rubric_id=rubric_id,
                dimension=dim.get("name", "unknown"),
                version=rubric.version,
            )
            count += 1

    return APIResponse(data={"reindexed_chunks": count})


# ── Disagreement Management ───────────────────────────────────────────────────

@router.get("/disagreements", response_model=APIResponse)
async def list_disagreements(
    current_user: DJIOrAdminUser,
    db: DB,
    severity: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    from sqlalchemy import func
    q = select(DisagreementRecord)
    if severity:
        q = q.where(DisagreementRecord.severity == severity)

    from sqlalchemy import select as sel, func as fn
    total = (await db.execute(
        sel(fn.count()).select_from(q.subquery())
    )).scalar_one()

    records = (await db.execute(
        q.order_by(DisagreementRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return APIResponse(data=PaginatedData(
        items=[DisagreementOut.model_validate(r) for r in records],
        total=total, page=page, page_size=page_size,
        has_next=(page * page_size) < total,
    ))


@router.get("/disagreements/{disagreement_id}", response_model=APIResponse)
async def get_disagreement(
    disagreement_id: UUID,
    current_user: DJIOrAdminUser,
    db: DB,
):
    result = await db.execute(
        select(DisagreementRecord).where(DisagreementRecord.id == disagreement_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("DisagreementRecord", str(disagreement_id))
    return APIResponse(data=DisagreementOut.model_validate(record))


@router.post("/disagreements/{disagreement_id}/mark-training-signal", response_model=APIResponse)
async def mark_training_signal(
    disagreement_id: UUID,
    current_user: AdminUser,
    db: DB,
):
    svc = DisagreementService(db)
    record = await svc.mark_training_signal(disagreement_id)
    return APIResponse(data=DisagreementOut.model_validate(record))


# ── Trace viewer ─────────────────────────────────────────────────────────────

@router.get("/trace/{review_id}", response_model=APIResponse)
async def get_evaluation_trace(
    review_id: UUID,
    current_user: DJIOrAdminUser,
    db: DB,
):
    from app.models.review import Review
    result = await db.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Review", str(review_id))
    return APIResponse(data={
        "review_id": str(review_id),
        "raw_llm_output": review.raw_llm_output,
        "confidence": review.confidence,
        "overall_score": review.overall_score,
    })
