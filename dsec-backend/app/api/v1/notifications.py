"""Notifications router."""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func

from app.core.dependencies import CurrentUser, DB
from app.models.audit import PortalNotification
from app.schemas.common import APIResponse, PaginatedData

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/my", response_model=APIResponse)
async def my_notifications(
    current_user: CurrentUser,
    db: DB,
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    q = select(PortalNotification).where(
        PortalNotification.user_id == current_user.id
    )
    if unread_only:
        q = q.where(PortalNotification.is_read.is_(False))

    total = (await db.execute(
        select(func.count()).select_from(q.subquery())
    )).scalar_one()

    notifications = (await db.execute(
        q.order_by(PortalNotification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return APIResponse(data=PaginatedData(
        items=[{
            "id": str(n.id),
            "event_type": n.event_type,
            "title": n.title,
            "body": n.body,
            "case_id": str(n.case_id) if n.case_id else None,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        } for n in notifications],
        total=total, page=page, page_size=page_size,
        has_next=(page * page_size) < total,
    ))


@router.put("/{notification_id}/read", response_model=APIResponse)
async def mark_read(notification_id: UUID, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(PortalNotification).where(
            PortalNotification.id == notification_id,
            PortalNotification.user_id == current_user.id,
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Notification", str(notification_id))
    notif.is_read = True
    return APIResponse(data={"marked_read": str(notification_id)})


@router.put("/read-all", response_model=APIResponse)
async def mark_all_read(current_user: CurrentUser, db: DB):
    from sqlalchemy import update
    await db.execute(
        update(PortalNotification)
        .where(PortalNotification.user_id == current_user.id)
        .values(is_read=True)
    )
    return APIResponse(data={"marked_read": "all"})
