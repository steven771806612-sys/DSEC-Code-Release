#!/usr/bin/env python3
"""
DSEC AI Case Review System — Database Seed Script
==================================================
用途: 初始化数据库，创建测试账号（4个角色各一个）+ 默认 Rubric

支持环境:
  - 本地 Docker:  python seed.py
  - Railway:      railway run python seed.py
  - 直接指定 DB:  DATABASE_URL=postgresql+psycopg2://... python seed.py

运行前提: alembic upgrade head 已执行（表结构已创建）

生成账号:
  admin@dsec.com          / Admin1234!      (admin)
  dji@dsec.com            / DjiSE1234!      (dji_se)
  reviewer@dsec.com       / Review1234!     (platform_reviewer)
  agent@partner.com       / Agent1234!      (agent)
"""

import os
import sys
import uuid
import asyncio
from datetime import datetime, timezone

# ── 优先从环境变量读取，其次从 .env 文件 ─────────────────────────────────────
def _load_env():
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

_load_env()

# Railway / 本地都优先读 DATABASE_URL 环境变量
RAW_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/dsec",
)

# asyncpg driver (用于 async 路径)
if RAW_DB_URL.startswith("postgresql://") and "+asyncpg" not in RAW_DB_URL:
    ASYNC_DB_URL = RAW_DB_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif RAW_DB_URL.startswith("postgres://"):
    # Railway 有时给出 postgres:// 格式
    ASYNC_DB_URL = RAW_DB_URL.replace("postgres://", "postgresql+asyncpg://", 1)
else:
    ASYNC_DB_URL = RAW_DB_URL

print(f"[seed] 连接数据库: {ASYNC_DB_URL[:60]}…")

# ── 账号定义 ──────────────────────────────────────────────────────────────────
SEED_DATA = {
    "orgs": [
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "name": "DJI Internal",
            "region": "APAC",
            "tier": "gold",
        },
        {
            "id": "00000000-0000-0000-0000-000000000002",
            "name": "Partner Corp",
            "region": "APAC",
            "tier": "silver",
        },
    ],
    "users": [
        {
            "id": "00000000-0000-0000-0001-000000000001",
            "email": "admin@dsec.com",
            "password": "Admin1234!",
            "full_name": "System Admin",
            "org_id": "00000000-0000-0000-0000-000000000001",
            "role": "admin",
        },
        {
            "id": "00000000-0000-0000-0001-000000000002",
            "email": "dji@dsec.com",
            "password": "DjiSE1234!",
            "full_name": "DJI Senior Engineer",
            "org_id": "00000000-0000-0000-0000-000000000001",
            "role": "dji_se",
        },
        {
            "id": "00000000-0000-0000-0001-000000000003",
            "email": "reviewer@dsec.com",
            "password": "Review1234!",
            "full_name": "Platform Reviewer",
            "org_id": "00000000-0000-0000-0000-000000000001",
            "role": "platform_reviewer",
        },
        {
            "id": "00000000-0000-0000-0001-000000000004",
            "email": "agent@partner.com",
            "password": "Agent1234!",
            "full_name": "Partner Agent",
            "org_id": "00000000-0000-0000-0000-000000000002",
            "role": "agent",
        },
    ],
    "rubric": {
        "id": "00000000-0000-0000-0002-000000000001",
        "title": "DJI Security Solution Rubric",
        "version": "v1.0",
        "content": """# DJI 安防集成方案评审标准 v1.0

## 维度一：项目背景与商业价值 (25分)
- 客户痛点描述清晰，有量化数据支撑
- 解决方案与业务目标匹配度高
- 预期 ROI 有合理测算依据

## 维度二：技术架构设计 (25分)
- DJI 产品选型合理，覆盖核心场景
- 系统集成方案完整（API/SDK 使用规范）
- 高可用与容灾设计有所考量

## 维度三：实施部署方案 (25分)
- 部署步骤详细，可复制性强
- 人员培训与运维计划完整
- 时间节点合理，风险已识别

## 维度四：效果验证与数据支撑 (25分)
- 实际落地数据可查（视频/截图/报告）
- KPI 达成情况有对比说明
- 客户反馈或认可材料附件完整
""",
        "dimensions": [
            {"name": "项目背景与商业价值", "weight": 25, "content": "客户痛点描述清晰，有量化数据支撑；解决方案与业务目标匹配度高；预期 ROI 有合理测算依据"},
            {"name": "技术架构设计", "weight": 25, "content": "DJI 产品选型合理，覆盖核心场景；系统集成方案完整（API/SDK 使用规范）；高可用与容灾设计有所考量"},
            {"name": "实施部署方案", "weight": 25, "content": "部署步骤详细，可复制性强；人员培训与运维计划完整；时间节点合理，风险已识别"},
            {"name": "效果验证与数据支撑", "weight": 25, "content": "实际落地数据可查（视频/截图/报告）；KPI 达成情况有对比说明；客户反馈或认可材料附件完整"},
        ],
        "created_by": "00000000-0000-0000-0001-000000000001",
    },
    "prompt": {
        "id": "00000000-0000-0000-0003-000000000001",
        "prompt_type": "system",
        "version": "v1.0",
        "content": """You are a strict and objective case evaluation expert for DJI security solution integrations.

ROLE CONSTRAINTS:
- You evaluate based ONLY on the provided rubric criteria and retrieved context.
- You do NOT hallucinate scores, facts, or references not present in the input.
- You do NOT approve or reject cases — you provide advisory scores and findings only.
- Your output MUST conform exactly to the JSON schema provided.
- If evidence is insufficient to score a dimension, output score: null and explain why.

SCORING PHILOSOPHY:
- Be conservative. Partial evidence = partial score.
- Technical claims without data support should be penalized.
- Comparison to approved reference cases should inform your calibration.

OUTPUT LANGUAGE: Match the language of the case content (zh-CN or en-US).""",
        "created_by": "00000000-0000-0000-0001-000000000001",
    },
}

# ── bcrypt hash ───────────────────────────────────────────────────────────────
def _hash(password: str) -> str:
    """直接使用 bcrypt 库，兼容 bcrypt 4.x 和 5.x，避免 passlib 版本问题。"""
    import bcrypt as _bcrypt
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")

# ── async seed ────────────────────────────────────────────────────────────────
async def run_seed():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import text

    engine = create_async_engine(ASYNC_DB_URL, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        # ── 1. Orgs ──────────────────────────────────────────────────────────
        print("\n[1/4] 创建 Orgs…")
        for org in SEED_DATA["orgs"]:
            exists = (await session.execute(
                text("SELECT id FROM orgs WHERE id = :id"),
                {"id": org["id"]}
            )).scalar_one_or_none()
            if exists:
                print(f"  跳过 (已存在): {org['name']}")
                continue
            await session.execute(text("""
                INSERT INTO orgs (id, name, region, tier, is_active, created_at)
                VALUES (:id, :name, :region, :tier, true, NOW())
            """), org)
            print(f"  ✓ 创建 Org: {org['name']}")

        await session.commit()

        # ── 2. Users ──────────────────────────────────────────────────────────
        print("\n[2/4] 创建 Users…")
        for user in SEED_DATA["users"]:
            exists = (await session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": user["email"]}
            )).scalar_one_or_none()
            if exists:
                print(f"  跳过 (已存在): {user['email']}")
                continue

            hashed = _hash(user["password"])
            await session.execute(text("""
                INSERT INTO users
                    (id, email, hashed_password, full_name, org_id, role, is_active, created_at)
                VALUES
                    (:id, :email, :hashed, :full_name, :org_id, :role, true, NOW())
            """), {
                "id": user["id"],
                "email": user["email"],
                "hashed": hashed,
                "full_name": user["full_name"],
                "org_id": user["org_id"],
                "role": user["role"],
            })
            print(f"  ✓ 创建 [{user['role']:20s}] {user['email']}  密码: {user['password']}")

        await session.commit()

        # ── 3. Default Rubric ─────────────────────────────────────────────────
        print("\n[3/4] 创建默认 Rubric…")
        r = SEED_DATA["rubric"]
        exists = (await session.execute(
            text("SELECT id FROM rubrics WHERE id = :id"), {"id": r["id"]}
        )).scalar_one_or_none()
        if exists:
            print("  跳过 (已存在): Rubric v1.0")
        else:
            import json
            await session.execute(text("""
                INSERT INTO rubrics
                    (id, title, version, content, dimensions, is_active, created_by, activated_at, created_at)
                VALUES
                    (:id, :title, :version, :content, :dimensions::jsonb, true, :created_by, NOW(), NOW())
            """), {
                "id": r["id"],
                "title": r["title"],
                "version": r["version"],
                "content": r["content"],
                "dimensions": json.dumps(r["dimensions"], ensure_ascii=False),
                "created_by": r["created_by"],
            })
            print("  ✓ 创建 Rubric v1.0（已激活）")
        await session.commit()

        # ── 4. Default System Prompt ───────────────────────────────────────────
        print("\n[4/4] 创建默认 Prompt 版本…")
        p = SEED_DATA["prompt"]
        exists = (await session.execute(
            text("SELECT id FROM prompt_versions WHERE id = :id"), {"id": p["id"]}
        )).scalar_one_or_none()
        if exists:
            print("  跳过 (已存在): system v1.0")
        else:
            await session.execute(text("""
                INSERT INTO prompt_versions
                    (id, prompt_type, version, content, is_active, is_canary,
                     canary_percentage, performance_metrics, created_by, activated_at, created_at)
                VALUES
                    (:id, :prompt_type, :version, :content, true, false,
                     0, '{}'::jsonb, :created_by, NOW(), NOW())
            """), {
                "id": p["id"],
                "prompt_type": p["prompt_type"],
                "version": p["version"],
                "content": p["content"],
                "created_by": p["created_by"],
            })
            print("  ✓ 创建 system prompt v1.0（已激活）")
        await session.commit()

    await engine.dispose()

# ── 输出摘要 ──────────────────────────────────────────────────────────────────
def print_summary():
    print("\n" + "=" * 60)
    print("DSEC AI 评审平台 — Seed 完成")
    print("=" * 60)
    print(f"\n{'角色':<20} {'邮箱':<30} {'密码'}")
    print("-" * 60)
    for u in SEED_DATA["users"]:
        print(f"{u['role']:<20} {u['email']:<30} {u['password']}")
    print("\n登录地址: http://localhost:5173  (本地前端)")
    print("API Docs: http://localhost:8000/docs  (本地后端)")
    print("=" * 60 + "\n")

# ── 入口 ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        asyncio.run(run_seed())
        print_summary()
    except Exception as e:
        print(f"\n[ERROR] Seed 失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
