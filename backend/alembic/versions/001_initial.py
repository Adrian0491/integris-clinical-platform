"""Initial schema — all CDTool tables.

Revision ID: 001_initial
Revises:
Create Date: 2026-05-22
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── tenants ──────────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False, server_default="trial"),
        sa.Column("hipaa_baa_signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="viewer"),
        sa.Column("mfa_secret", sa.String(255), nullable=True),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── studies ───────────────────────────────────────────────────────────────
    op.create_table(
        "studies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("study_id", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("phase", sa.String(20), nullable=True),
        sa.Column("therapeutic_area", sa.String(255), nullable=True),
        sa.Column("sponsor", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "study_id", name="uq_studies_tenant_study"),
    )
    op.create_index("ix_studies_tenant_id", "studies", ["tenant_id"])

    # ── datasets ──────────────────────────────────────────────────────────────
    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "study_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("storage_uri", sa.String(1000), nullable=False),
        sa.Column("file_format", sa.String(20), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_datasets_tenant_id", "datasets", ["tenant_id"])
    op.create_index("ix_datasets_study_id", "datasets", ["study_id"])

    # ── validation_jobs ───────────────────────────────────────────────────────
    op.create_table(
        "validation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "study_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "submitted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("dataset_ids", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("rule_profile", sa.String(100), nullable=False, server_default="sdtm_default"),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_validation_jobs_tenant_id", "validation_jobs", ["tenant_id"])
    op.create_index("ix_validation_jobs_study_id", "validation_jobs", ["study_id"])

    # ── findings ──────────────────────────────────────────────────────────────
    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("validation_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "study_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("finding_type", sa.String(50), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("domain", sa.String(50), nullable=False),
        sa.Column("field", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("usubjid", sa.String(255), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column(
            "resolved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_findings_tenant_id", "findings", ["tenant_id"])
    op.create_index("ix_findings_job_id", "findings", ["job_id"])
    op.create_index("ix_findings_study_id", "findings", ["study_id"])
    op.create_index("ix_findings_rule_id", "findings", ["rule_id"])
    op.create_index("ix_findings_severity", "findings", ["severity"])
    op.create_index("ix_findings_domain", "findings", ["domain"])
    op.create_index("ix_findings_usubjid", "findings", ["usubjid"])
    op.create_index("ix_findings_status", "findings", ["status"])

    # ── compliance_reports ────────────────────────────────────────────────────
    op.create_table(
        "compliance_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("validation_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "study_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("studies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report_type", sa.String(50), nullable=False, server_default="sdtm_validation"),
        sa.Column("storage_uri", sa.String(1000), nullable=True),
        sa.Column(
            "generated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "signed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_compliance_reports_tenant_id", "compliance_reports", ["tenant_id"])
    op.create_index("ix_compliance_reports_job_id", "compliance_reports", ["job_id"])
    op.create_index("ix_compliance_reports_study_id", "compliance_reports", ["study_id"])

    # ── electronic_signatures ─────────────────────────────────────────────────
    op.create_table(
        "electronic_signatures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meaning", sa.String(50), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signature_hash", sa.String(64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_electronic_signatures_tenant_id", "electronic_signatures", ["tenant_id"])
    op.create_index("ix_electronic_signatures_user_id", "electronic_signatures", ["user_id"])
    op.create_index("ix_electronic_signatures_target_id", "electronic_signatures", ["target_id"])

    # ── audit_log ─────────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("before_hash", sa.String(64), nullable=True),
        sa.Column("after_hash", sa.String(64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_log_tenant_id", "audit_log", ["tenant_id"])
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_occurred_at", "audit_log", ["occurred_at"])

    # ── rule_profiles ─────────────────────────────────────────────────────────
    op.create_table(
        "rule_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("base_profile", sa.String(100), nullable=False, server_default="sdtm_default"),
        sa.Column("overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_rule_profiles_tenant_name"),
    )
    op.create_index("ix_rule_profiles_tenant_id", "rule_profiles", ["tenant_id"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("rule_profiles")
    op.drop_table("audit_log")
    op.drop_table("electronic_signatures")
    op.drop_table("compliance_reports")
    op.drop_table("findings")
    op.drop_table("validation_jobs")
    op.drop_table("datasets")
    op.drop_table("studies")
    op.drop_table("users")
    op.drop_table("tenants")
