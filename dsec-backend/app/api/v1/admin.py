"""Admin router — database initialization and admin utilities."""
from typing import Any
from fastapi import APIRouter
from sqlalchemy import select

from app.core.database import get_db
from app.core.dependencies import DB
from app.core.security import hash_password
from app.models.user import User, Org, Department, RoleEnum
from app.schemas.common import APIResponse

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Seed data definitions
# ---------------------------------------------------------------------------

_ORGS = [
    {"name": "DJI Internal", "region": "global", "tier": "gold", "_key": "dji"},
    {"name": "DSEC Platform", "region": "global", "tier": "gold", "_key": "dsec"},
    {"name": "Partner Agency", "region": "us-east", "tier": "silver", "_key": "partner"},
]

_DEPARTMENTS = [
    # (org_key, name, is_dji_internal)
    ("dji", "Security Engineering", True),
    ("dsec", "Platform Operations", False),
]

_USERS = [
    {
        "email": "admin@dsec.com",
        "password": "Admin1234!",
        "full_name": "DSEC Admin",
        "role": RoleEnum.ADMIN,
        "org_key": "dsec",
    },
    {
        "email": "dji@dsec.com",
        "password": "DjiSE1234!",
        "full_name": "DJI Security Engineer",
        "role": RoleEnum.DJI_SE,
        "org_key": "dji",
    },
    {
        "email": "reviewer@dsec.com",
        "password": "Review1234!",
        "full_name": "Platform Reviewer",
        "role": RoleEnum.PLATFORM_REVIEWER,
        "org_key": "dsec",
    },
    {
        "email": "agent@partner.com",
        "password": "Agent1234!",
        "full_name": "Partner Agent",
        "role": RoleEnum.AGENT,
        "org_key": "partner",
    },
]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/init-db", response_model=APIResponse)
async def init_db(db: DB):
    """Idempotently seed the database with organisations and test accounts.

    Safe to call multiple times — existing records are left untouched.
    Returns a summary of what was created vs. what already existed.
    """
    created_orgs: list[str] = []
    skipped_orgs: list[str] = []
    created_users: list[str] = []
    skipped_users: list[str] = []

    # ── 1. Ensure organisations exist ──────────────────────────────────────
    org_map: dict[str, Org] = {}
    for org_def in _ORGS:
        key = org_def["_key"]
        name = org_def["name"]

        result = await db.execute(select(Org).where(Org.name == name))
        existing_org = result.scalar_one_or_none()

        if existing_org:
            org_map[key] = existing_org
            skipped_orgs.append(name)
        else:
            new_org = Org(
                name=name,
                region=org_def.get("region"),
                tier=org_def.get("tier"),
            )
            db.add(new_org)
            await db.flush()  # populate new_org.id
            org_map[key] = new_org
            created_orgs.append(name)

    # ── 2. Ensure departments exist ────────────────────────────────────────
    for org_key, dept_name, is_dji_internal in _DEPARTMENTS:
        org = org_map.get(org_key)
        if org is None:
            continue

        result = await db.execute(
            select(Department).where(
                Department.org_id == org.id,
                Department.name == dept_name,
            )
        )
        if result.scalar_one_or_none() is None:
            db.add(Department(org_id=org.id, name=dept_name, is_dji_internal=is_dji_internal))

    await db.flush()

    # ── 3. Ensure users exist ──────────────────────────────────────────────
    for user_def in _USERS:
        email = user_def["email"]

        result = await db.execute(select(User).where(User.email == email))
        if result.scalar_one_or_none():
            skipped_users.append(email)
            continue

        org = org_map.get(user_def["org_key"])
        if org is None:
            # Should never happen given the org definitions above
            skipped_users.append(f"{email} (org not found)")
            continue

        new_user = User(
            email=email,
            hashed_password=hash_password(user_def["password"]),
            full_name=user_def.get("full_name"),
            org_id=org.id,
            role=user_def["role"],
        )
        db.add(new_user)
        created_users.append(email)

    await db.flush()

    return APIResponse(
        data={
            "orgs": {
                "created": created_orgs,
                "skipped": skipped_orgs,
            },
            "users": {
                "created": created_users,
                "skipped": skipped_users,
            },
        }
    )
