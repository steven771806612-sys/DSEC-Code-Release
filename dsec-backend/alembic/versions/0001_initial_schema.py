"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── Enums ────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE role_enum AS ENUM (
                'agent', 'platform_reviewer', 'dji_se', 'admin'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE case_status_enum AS ENUM (
                'DRAFT','SUBMITTED','AI_REVIEWED',
                'PLATFORM_REVIEWED','DJI_REVIEWED','APPROVED','REJECTED'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE page_type_enum AS ENUM (
                'overview','architecture','deployment','results','appendix'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE review_type_enum AS ENUM ('ai','platform','dji');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE task_status_enum AS ENUM (
                'pending','in_progress','completed','skipped'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE decision_enum AS ENUM (
                'approve','reject','revise','pending'
            );
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # ── Identity & Access ────────────────────────────────────
    op.create_table(
        "orgs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("region", sa.String(50)),
        sa.Column("tier", sa.String(20)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "departments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_dji_internal", sa.Boolean, server_default="false"),
    )

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.Text, nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("department_id", UUID(as_uuid=True), sa.ForeignKey("departments.id")),
        sa.Column("role", sa.Enum(name="role_enum"), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── Case Domain ──────────────────────────────────────────
    op.create_table(
        "cases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("orgs.id"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("industry", sa.String(100)),
        sa.Column("region", sa.String(50)),
        sa.Column("status", sa.Enum(name="case_status_enum"), server_default="DRAFT"),
        sa.Column("current_version_id", UUID(as_uuid=True)),
        sa.Column("rubric_version", sa.String(20), server_default="v1.0"),
        sa.Column("tags", JSONB, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_cases_org_status", "cases", ["org_id", "status"])
    op.create_index("ix_cases_status", "cases", ["status"])

    op.create_table(
        "case_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("submitted_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("change_summary", sa.Text),
        sa.Column("is_current", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "case_pages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("case_version_id", UUID(as_uuid=True), sa.ForeignKey("case_versions.id"), nullable=False),
        sa.Column("page_number", sa.Integer, nullable=False),
        sa.Column("page_type", sa.Enum(name="page_type_enum")),
        sa.Column("title", sa.String(512)),
        sa.Column("content_text", sa.Text),
        sa.Column("content_html", sa.Text),
        sa.Column("word_count", sa.Integer, server_default="0"),
        sa.Column("has_images", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_case_pages_version", "case_pages", ["case_version_id"])

    op.create_table(
        "attachments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("case_version_id", UUID(as_uuid=True), sa.ForeignKey("case_versions.id"), nullable=False),
        sa.Column("file_name", sa.String(512), nullable=False),
        sa.Column("file_type", sa.String(50)),
        sa.Column("s3_key", sa.Text, nullable=False),
        sa.Column("file_size_bytes", sa.Integer),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_primary", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Review Domain ────────────────────────────────────────
    op.create_table(
        "review_tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("review_type", sa.Enum(name="review_type_enum"), nullable=False),
        sa.Column("assigned_to", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("status", sa.Enum(name="task_status_enum"), server_default="pending"),
        sa.Column("priority", sa.Integer, server_default="3"),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("sla_breached", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("case_version_id", UUID(as_uuid=True), sa.ForeignKey("case_versions.id"), nullable=False),
        sa.Column("review_task_id", UUID(as_uuid=True), sa.ForeignKey("review_tasks.id"), nullable=False),
        sa.Column("reviewer_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("review_type", sa.Enum(name="review_type_enum"), nullable=False),
        sa.Column("overall_score", sa.Float),
        sa.Column("dimension_scores", JSONB, server_default="{}"),
        sa.Column("issues", JSONB, server_default="[]"),
        sa.Column("recommendations", JSONB, server_default="[]"),
        sa.Column("decision", sa.Enum(name="decision_enum")),
        sa.Column("confidence", sa.Float),
        sa.Column("is_override", sa.Boolean, server_default="false"),
        sa.Column("override_reason", sa.Text),
        sa.Column("raw_llm_output", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_reviews_case", "reviews", ["case_id", "review_type"])

    # ── Rubric & Prompts ─────────────────────────────────────
    op.create_table(
        "rubrics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("content", sa.Text),
        sa.Column("dimensions", JSONB, server_default="[]"),
        sa.Column("is_active", sa.Boolean, server_default="false"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "prompt_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("prompt_type", sa.String(50), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="false"),
        sa.Column("is_canary", sa.Boolean, server_default="false"),
        sa.Column("canary_percentage", sa.Float, server_default="0"),
        sa.Column("performance_metrics", JSONB, server_default="{}"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("deprecated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Vector Tables ────────────────────────────────────────
    op.execute("""
        CREATE TABLE rubric_vectors (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            content     TEXT NOT NULL,
            embedding   vector(1536),
            rubric_id   UUID REFERENCES rubrics(id),
            dimension   TEXT,
            version     TEXT,
            industry    JSONB DEFAULT '[]',
            region      JSONB DEFAULT '[]',
            weight      FLOAT DEFAULT 1.0,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE case_vectors (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            content         TEXT NOT NULL,
            embedding       vector(1536),
            case_page_id    UUID REFERENCES case_pages(id),
            case_id         UUID REFERENCES cases(id),
            page_type       TEXT,
            industry        TEXT,
            region          TEXT,
            overall_score   FLOAT,
            label_source    TEXT,
            status          TEXT,
            rubric_version  TEXT,
            is_correction   BOOL DEFAULT FALSE,
            weight_boost    FLOAT DEFAULT 1.0,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE review_vectors (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            content     TEXT NOT NULL,
            embedding   vector(1536),
            review_id   UUID REFERENCES reviews(id),
            review_type TEXT,
            dimension   TEXT,
            decision    TEXT,
            score       FLOAT,
            industry    TEXT,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # ── Disagreement & Audit ─────────────────────────────────
    op.create_table(
        "disagreement_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("case_page_id", UUID(as_uuid=True), sa.ForeignKey("case_pages.id")),
        sa.Column("ai_review_id", UUID(as_uuid=True), sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("human_review_id", UUID(as_uuid=True), sa.ForeignKey("reviews.id"), nullable=False),
        sa.Column("disagreement_type", sa.String(50)),
        sa.Column("ai_score", sa.Float),
        sa.Column("human_score", sa.Float),
        sa.Column("score_gap", sa.Float),
        sa.Column("severity", sa.String(20)),
        sa.Column("dimension", sa.String(200)),
        sa.Column("ai_reasoning", sa.Text),
        sa.Column("human_reasoning", sa.Text),
        sa.Column("is_training_signal", sa.Boolean, server_default="false"),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_disagreements_severity", "disagreement_records", ["severity", "created_at"])

    op.execute("""
        CREATE TABLE disagreement_vectors (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            content             TEXT NOT NULL,
            embedding           vector(1536),
            disagreement_id     UUID REFERENCES disagreement_records(id),
            dimension           TEXT,
            severity            TEXT,
            is_correction       BOOL DEFAULT TRUE,
            weight_boost        FLOAT DEFAULT 1.5,
            created_at          TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("actor_id", UUID(as_uuid=True)),
        sa.Column("actor_role", sa.String(50)),
        sa.Column("action", sa.String(200), nullable=False),
        sa.Column("resource_type", sa.String(50)),
        sa.Column("resource_id", UUID(as_uuid=True)),
        sa.Column("old_value", JSONB),
        sa.Column("new_value", JSONB),
        sa.Column("ip_address", sa.String(50)),
        sa.Column("user_agent", sa.Text),
        sa.Column("request_id", sa.String(100)),
        sa.Column("result", sa.String(20), server_default="success"),
        sa.Column("error_message", sa.Text),
    )
    op.create_index("ix_audit_actor", "audit_logs", ["actor_id", "timestamp"])
    op.create_index("ix_audit_resource", "audit_logs", ["resource_type", "resource_id"])

    op.create_table(
        "portal_notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(512)),
        sa.Column("body", sa.Text),
        sa.Column("case_id", UUID(as_uuid=True)),
        sa.Column("is_read", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user", "portal_notifications", ["user_id", "created_at"])

    # ── Vector Indexes (IVFFlat) ─────────────────────────────
    op.execute("""
        CREATE INDEX ON rubric_vectors
            USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10)
    """)
    op.execute("""
        CREATE INDEX ON case_vectors
            USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10)
    """)
    op.execute("""
        CREATE INDEX ON review_vectors
            USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10)
    """)
    op.execute("""
        CREATE INDEX ON disagreement_vectors
            USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10)
    """)


def downgrade() -> None:
    op.drop_table("portal_notifications")
    op.drop_table("audit_logs")
    op.execute("DROP TABLE IF EXISTS disagreement_vectors")
    op.drop_table("disagreement_records")
    op.execute("DROP TABLE IF EXISTS review_vectors")
    op.execute("DROP TABLE IF EXISTS case_vectors")
    op.execute("DROP TABLE IF EXISTS rubric_vectors")
    op.drop_table("prompt_versions")
    op.drop_table("rubrics")
    op.drop_table("reviews")
    op.drop_table("review_tasks")
    op.drop_table("attachments")
    op.drop_table("case_pages")
    op.drop_table("case_versions")
    op.drop_table("cases")
    op.drop_table("users")
    op.drop_table("departments")
    op.drop_table("orgs")
    for enum_name in [
        "decision_enum", "task_status_enum", "review_type_enum",
        "page_type_enum", "case_status_enum", "role_enum",
    ]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
