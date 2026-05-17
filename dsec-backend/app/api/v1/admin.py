"""Admin router — database initialization and admin utilities."""
from fastapi import APIRouter
from sqlalchemy import select

from app.core.dependencies import DB
from app.core.security import hash_password
from app.models.user import User, Org, RoleEnum
from app.schemas.common import APIResponse

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Test accounts
# ---------------------------------------------------------------------------

_TEST_USERS = [
    {
        "email": "admin@dsec.com",
        "password": "Admin1234!",
        "full_name": "DSEC Admin",
        "role": RoleEnum.ADMIN,
    },
    {
        "email": "dji@dsec.com",
        "password": "DjiSE1234!",
        "full_name": "DJI Security Engineer",
        "role": RoleEnum.DJI_SE,
    },
    {
        "email": "reviewer@dsec.com",
        "password": "Review1234!",
        "full_name": "Platform Reviewer",
        "role": RoleEnum.PLATFORM_REVIEWER,
    },
    {
        "email": "agent@partner.com",
        "password": "Agent1234!",
        "full_name": "Partner Agent",
        "role": RoleEnum.AGENT,
    },
]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/init-db", response_model=APIResponse)
async def init_db(db: DB):
    """Idempotently seed the database with a default org and test accounts.

    Safe to call multiple times — existing records are left untouched.
    Returns a summary of what was created vs. what already existed.
    """
    created_users: list[str] = []
    skipped_users: list[str] = []

    # ── 1. Ensure a default org exists ─────────────────────────────────────
    result = await db.execute(select(Org).where(Org.name == "DSEC Platform"))
    org = result.scalar_one_or_none()

    if org is None:
        org = Org(name="DSEC Platform", region="global", tier="gold")
        db.add(org)
        await db.flush()  # populate org.id before referencing it

    # ── 2. Ensure test users exist ─────────────────────────────────────────
    for user_def in _TEST_USERS:
        email = user_def["email"]

        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none() is not None:
            skipped_users.append(email)
            continue

        new_user = User(
            email=email,
            hashed_password=hash_password(user_def["password"]),
            full_name=user_def["full_name"],
            org_id=org.id,
            role=user_def["role"],
        )
        db.add(new_user)
        created_users.append(email)

    await db.flush()

    return APIResponse(
        data={
            "users": {
                "created": created_users,
                "skipped": skipped_users,
            },
        }
    )
