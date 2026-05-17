"""Auth router — login, refresh, register."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, DB
from app.core.security import (
    verify_password, hash_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.core.config import settings
from app.models.user import User, Org, RoleEnum
from app.schemas.user import LoginRequest, TokenResponse, UserCreate, UserOut, OrgCreate, OrgOut
from app.schemas.common import APIResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=APIResponse)
async def login(payload: LoginRequest, db: DB):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    user.last_login_at = datetime.now(timezone.utc)

    access_token = create_access_token(
        subject=str(user.id),
        org_id=str(user.org_id),
        role=user.role.value,
    )
    refresh_token = create_refresh_token(subject=str(user.id))

    return APIResponse(
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    )


@router.post("/refresh", response_model=APIResponse)
async def refresh_token(refresh_token: str, db: DB):
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = create_access_token(
        subject=str(user.id),
        org_id=str(user.org_id),
        role=user.role.value,
    )
    return APIResponse(
        data={"access_token": access_token, "token_type": "bearer"}
    )


@router.get("/me", response_model=APIResponse)
async def get_me(current_user: CurrentUser):
    return APIResponse(data=UserOut.model_validate(current_user))


@router.post("/register", response_model=APIResponse)
async def register(payload: UserCreate, db: DB):
    """Self-registration (agent role only). Admin can create any role."""
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        org_id=payload.org_id,
        role=RoleEnum.AGENT,  # Self-registration always creates Agent
    )
    db.add(user)
    await db.flush()
    return APIResponse(data=UserOut.model_validate(user))


# ── Org endpoints ──────────────────────────────────────────────────────────
@router.post("/orgs", response_model=APIResponse)
async def create_org(payload: OrgCreate, db: DB):
    org = Org(**payload.model_dump())
    db.add(org)
    await db.flush()
    return APIResponse(data=OrgOut.model_validate(org))
