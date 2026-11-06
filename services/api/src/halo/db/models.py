"""Business records. Restricted rows carry organization_id and workspace_id."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    desc,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from halo.db.base import Base

UUID_PK = UUID(as_uuid=True)


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(UUID_PK, primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _updated() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = _id()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()

    __table_args__ = (CheckConstraint("mode IN ('fixture', 'live')", name="ck_organizations_mode"),)


class Principal(Base):
    __tablename__ = "principals"

    id: Mapped[uuid.UUID] = _id()
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    oidc_subject: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (CheckConstraint("kind IN ('user', 'service')", name="ck_principals_kind"),)


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    principal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("principal_id", "organization_id", name="uq_org_membership"),
        ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_org_membership_org"),
    )


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    classification: Mapped[str] = mapped_column(String(64), nullable=False, default="internal")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()

    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_workspaces_org_id"),
        CheckConstraint("kind IN ('fund', 'company')", name="ck_workspaces_kind"),
        ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_workspaces_org"),
        ForeignKeyConstraint(
            ["organization_id", "id", "company_id"],
            ["companies.organization_id", "companies.workspace_id", "companies.id"],
            name="fk_workspaces_company",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
    )


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    principal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(ARRAY(String(64)), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("principal_id", "workspace_id", name="uq_workspace_membership"),
        UniqueConstraint(
            "organization_id", "workspace_id", "id", name="uq_workspace_memberships_scope_id"
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_workspace_memberships_workspace",
        ),
        Index("ix_workspace_memberships_ws_created", "workspace_id", desc("created_at")),
    )


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    legal_name: Mapped[str] = mapped_column(String(300), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    website: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()

    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_companies_scope_id"),
        CheckConstraint(
            "stage IN ('discovered','first_look','diligence','ic_review','closing',"
            "'owned','exited','passed','paused','term_sheet','partner_review')",
            name="ck_companies_stage",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_companies_workspace",
        ),
        Index("ix_companies_ws_created", "workspace_id", desc("created_at")),
        Index("ix_companies_stage", "stage"),
    )


class InvestmentCase(Base):
    __tablename__ = "investment_cases"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    case_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    phase: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    on_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    monitor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    phase_entered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    reason_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()

    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_cases_scope_id"),
        CheckConstraint(
            "case_type IN ('initial', 'follow_on', 'secondary', 'exit')",
            name="ck_cases_type",
        ),
        CheckConstraint(
            "phase IN ('sourcing','screening','partner_review','due_diligence',"
            "'investment_committee','term_sheet','negotiation_closing','unknown')",
            name="ck_cases_phase",
        ),
        CheckConstraint("outcome IN ('open','passed','portfolio')", name="ck_cases_outcome"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_cases_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "company_id"],
            ["companies.organization_id", "companies.workspace_id", "companies.id"],
            name="fk_cases_company",
        ),
        Index("ix_cases_ws_created", "workspace_id", desc("created_at")),
        Index("ix_cases_due", "due_at"),
        Index("ix_cases_company_phase", "company_id", "phase", "outcome"),
    )


class AgentAssignment(Base):
    """One project an agent performs for a company. The same agent may hold several."""

    __tablename__ = "agent_assignments"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(32), nullable=False)
    investment_process_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    waiting_on: Mapped[str] = mapped_column(Text, nullable=False, default="")
    agent_config_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    supersedes_assignment_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()

    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_assignments_scope_id"),
        CheckConstraint(
            "status IN ('queued','active','waiting_for_input','blocked','paused','completed','cancelled')",
            name="ck_assignments_status",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_assignments_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "company_id"],
            ["companies.organization_id", "companies.workspace_id", "companies.id"],
            name="fk_assignments_company",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "investment_process_id"],
            ["investment_cases.organization_id", "investment_cases.workspace_id", "investment_cases.id"],
            name="fk_assignments_process",
        ),
        Index("ix_assignments_company_agent_status", "company_id", "agent_id", "status"),
        Index("ix_assignments_process", "investment_process_id"),
    )


class StageEvent(Base):
    """Append-only authorized stage transition. The company stage trigger requires one."""

    __tablename__ = "stage_events"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    case_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    from_stage: Mapped[str] = mapped_column(String(32), nullable=False)
    to_stage: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_stage_events_scope_id"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_stage_events_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "company_id"],
            ["companies.organization_id", "companies.workspace_id", "companies.id"],
            name="fk_stage_events_company",
        ),
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    logical_doc_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    mime: Mapped[str] = mapped_column(String(120), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    classification: Mapped[str] = mapped_column(String(64), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    usage_policy: Mapped[str] = mapped_column(String(64), nullable=False)
    ingestion_status: Mapped[str] = mapped_column(String(32), nullable=False)
    origin_class: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_documents_scope_id"),
        UniqueConstraint("logical_doc_id", "version", name="uq_documents_logical_version"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_documents_workspace",
        ),
        Index("ix_documents_ws_created", "workspace_id", desc("created_at")),
        Index("ix_documents_sha", "organization_id", "sha256"),
    )


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    locator_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    observed_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sample_size: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    definition_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    independence_group: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    origin_class: Mapped[str] = mapped_column(String(64), nullable=False)
    limitations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_evidence_scope_id"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_evidence_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "document_id"],
            ["documents.organization_id", "documents.workspace_id", "documents.id"],
            name="fk_evidence_document",
        ),
        Index("ix_evidence_ws_created", "workspace_id", desc("created_at")),
    )


class EvidenceSnapshot(Base):
    __tablename__ = "evidence_snapshots"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    case_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    manifest_key: Mapped[str] = mapped_column(String(500), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    frozen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_snapshots_scope_id"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_snapshots_workspace",
        ),
    )


class SnapshotEvidence(Base):
    __tablename__ = "snapshot_evidence"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_snapshot_evidence_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "snapshot_id"],
            ["evidence_snapshots.organization_id", "evidence_snapshots.workspace_id", "evidence_snapshots.id"],
            name="fk_snapshot_evidence_snapshot",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "evidence_id"],
            ["evidence_records.organization_id", "evidence_records.workspace_id", "evidence_records.id"],
            name="fk_snapshot_evidence_evidence",
        ),
    )


class FundBundleItem(Base):
    __tablename__ = "fund_bundle_items"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    fund_snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    source_workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    source_record_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    source_record_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    source_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    projected_fields: Mapped[dict] = mapped_column(JSONB, nullable=False)
    scope_grant_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_fund_bundle_scope_id"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_fund_bundle_workspace",
        ),
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    case_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    agent_name: Mapped[str] = mapped_column(String(32), nullable=False)
    phase: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    workflow_id: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    budget_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    status_detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()

    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_runs_scope_id"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "assignment_id"],
            ["agent_assignments.organization_id", "agent_assignments.workspace_id", "agent_assignments.id"],
            name="fk_runs_assignment",
        ),
        Index("ix_runs_assignment_created", "assignment_id", desc("created_at")),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_runs_workspace",
        ),
        Index("ix_runs_status", "status"),
        Index("ix_runs_ws_created", "workspace_id", desc("created_at")),
    )


class RunGrant(Base):
    __tablename__ = "run_grants"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    resource_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    allowed_operation: Mapped[str] = mapped_column(String(32), nullable=False)
    phase: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_run_grants_scope_id"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_run_grants_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "run_id"],
            ["agent_runs.organization_id", "agent_runs.workspace_id", "agent_runs.id"],
            name="fk_run_grants_run",
        ),
    )


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    phase: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    content_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_artifacts_scope_id"),
        UniqueConstraint("run_id", "phase", "kind", "version", name="uq_artifacts_run_phase_kind"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_artifacts_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "run_id"],
            ["agent_runs.organization_id", "agent_runs.workspace_id", "agent_runs.id"],
            name="fk_artifacts_run",
        ),
        Index("ix_artifacts_ws_created", "workspace_id", desc("created_at")),
    )


class ArtifactDependency(Base):
    __tablename__ = "artifact_dependencies"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    artifact_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    dependency_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    dependency_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    dependency_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_artifact_deps_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "artifact_id"],
            ["artifacts.organization_id", "artifacts.workspace_id", "artifacts.id"],
            name="fk_artifact_deps_artifact",
        ),
    )


class ArtifactSourceScope(Base):
    __tablename__ = "artifact_source_scopes"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    artifact_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    source_workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    source_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    visibility_requirement: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_artifact_scopes_workspace",
        ),
    )


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    artifact_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    materiality: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    limitations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    validation_question: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_findings_scope_id"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_findings_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "artifact_id"],
            ["artifacts.organization_id", "artifacts.workspace_id", "artifacts.id"],
            name="fk_findings_artifact",
        ),
    )


class FindingEvidence(Base):
    __tablename__ = "finding_evidence"

    finding_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True)
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    relationship: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "relationship IN ('support', 'contradict', 'context')",
            name="ck_finding_evidence_rel",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_finding_evidence_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "finding_id"],
            ["findings.organization_id", "findings.workspace_id", "findings.id"],
            name="fk_finding_evidence_finding",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "evidence_id"],
            ["evidence_records.organization_id", "evidence_records.workspace_id", "evidence_records.id"],
            name="fk_finding_evidence_evidence",
        ),
    )


class Concern(Base):
    __tablename__ = "concerns"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()

    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_concerns_scope_id"),
        CheckConstraint("severity IN ('critical', 'material', 'question')", name="ck_concerns_severity"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_concerns_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "case_id"],
            ["investment_cases.organization_id", "investment_cases.workspace_id", "investment_cases.id"],
            name="fk_concerns_case",
        ),
        Index(
            "ix_concerns_open_blocking",
            "workspace_id",
            "due_at",
            postgresql_where=text("status = 'open' AND blocking"),
        ),
    )


class ConcernDisposition(Base):
    __tablename__ = "concern_dispositions"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    concern_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    disposition: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_ids: Mapped[list] = mapped_column(ARRAY(UUID_PK), nullable=False, default=list)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        CheckConstraint(
            "disposition IN ('resolved', 'accepted', 'waived')",
            name="ck_dispositions",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_dispositions_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "concern_id"],
            ["concerns.organization_id", "concerns.workspace_id", "concerns.id"],
            name="fk_dispositions_concern",
        ),
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    artifact_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        CheckConstraint(
            "verdict IN ('approve_draft', 'request_changes', 'reject_unsupported')",
            name="ck_reviews_verdict",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_reviews_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "artifact_id"],
            ["artifacts.organization_id", "artifacts.workspace_id", "artifacts.id"],
            name="fk_reviews_artifact",
        ),
    )


class IcPacket(Base):
    __tablename__ = "ic_packets"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    manifest_key: Mapped[str] = mapped_column(String(500), nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    artifact_ids: Mapped[list] = mapped_column(ARRAY(UUID_PK), nullable=False, default=list)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_packets_scope_id"),
        UniqueConstraint("case_id", "version", name="uq_packets_case_version"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_packets_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "case_id"],
            ["investment_cases.organization_id", "investment_cases.workspace_id", "investment_cases.id"],
            name="fk_packets_case",
        ),
    )


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    packet_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False, unique=True)
    packet_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        CheckConstraint(
            "decision IN ('approve', 'pass', 'defer', 'terms_revision')",
            name="ck_decisions_decision",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_decisions_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "packet_id"],
            ["ic_packets.organization_id", "ic_packets.workspace_id", "ic_packets.id"],
            name="fk_decisions_packet",
        ),
    )


class CloseRecord(Base):
    __tablename__ = "close_records"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_close_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "case_id"],
            ["investment_cases.organization_id", "investment_cases.workspace_id", "investment_cases.id"],
            name="fk_close_case",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "document_id"],
            ["documents.organization_id", "documents.workspace_id", "documents.id"],
            name="fk_close_document",
        ),
    )


class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(32), nullable=False)
    cadence: Mapped[str] = mapped_column(String(32), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    freshness_limit_days: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "slug", "formula_version", name="uq_metric_def_slug"
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_metric_def_workspace",
        ),
    )


class MetricObservation(Base):
    __tablename__ = "metric_observations"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    definition_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    completeness: Mapped[str] = mapped_column(String(32), nullable=False)
    missing_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint(
            "definition_id", "period_start", "period_end", name="uq_metric_obs_period"
        ),
        CheckConstraint(
            "(value IS NOT NULL AND completeness = 'complete') OR "
            "(value IS NULL AND completeness IN ('missing', 'invalid'))",
            name="ck_metric_obs_missing",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_metric_obs_workspace",
        ),
        ForeignKeyConstraint(
            ["definition_id"],
            ["metric_definitions.id"],
            name="fk_metric_obs_definition",
        ),
        Index("ix_metric_obs_def_period", "definition_id", "period_start"),
    )


class Initiative(Base):
    __tablename__ = "initiatives"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(32), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    approval_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    baseline: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    measurement_plan: Mapped[str] = mapped_column(Text, nullable=False, default="")
    costs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()

    __table_args__ = (
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_initiatives_scope_id"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_initiatives_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "company_id"],
            ["companies.organization_id", "companies.workspace_id", "companies.id"],
            name="fk_initiatives_company",
        ),
    )


class ValueEntry(Base):
    __tablename__ = "value_entries"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    initiative_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    metric: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    source_ids: Mapped[list] = mapped_column(ARRAY(UUID_PK), nullable=False, default=list)
    verifier_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    period: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        CheckConstraint(
            "classification IN ('observed', 'estimated', 'verified', 'unverified')",
            name="ck_value_classification",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_value_workspace",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "initiative_id"],
            ["initiatives.organization_id", "initiatives.workspace_id", "initiatives.id"],
            name="fk_value_initiative",
        ),
    )


class Playbook(Base):
    __tablename__ = "playbooks"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_key: Mapped[str] = mapped_column(String(500), nullable=False)
    declassification_review_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    allowed_audience: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_playbooks_workspace",
        ),
    )


class ReportRelease(Base):
    __tablename__ = "report_releases"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    artifact_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    audience: Mapped[str] = mapped_column(String(120), nullable=False)
    approver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_releases_workspace",
        ),
    )


class BudgetReservation(Base):
    __tablename__ = "budget_reservations"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    cap: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    reserved: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=Decimal("0"))
    actual: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_budgets_workspace",
        ),
    )


class ProviderCall(Base):
    __tablename__ = "provider_calls"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_request_id: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    result_status: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_provider_calls_workspace",
        ),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    before_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    after_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    payload_redacted: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_audit_workspace",
        ),
        Index("ix_audit_ws_created", "workspace_id", desc("created_at")),
    )


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    payload_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_outbox_workspace",
        ),
        Index(
            "ix_outbox_pending",
            "lease_until",
            postgresql_where=text("status = 'pending'"),
        ),
    )


class ActivityOutcome(Base):
    __tablename__ = "activity_outcomes"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    activity_execution_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    result_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_activity_workspace",
        ),
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    principal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    route: Mapped[str] = mapped_column(String(200), nullable=False)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("principal_id", "route", "key", name="uq_idempotency"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = _id()
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    principal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()

    __table_args__ = (
        UniqueConstraint("event_id", "principal_id", name="uq_notifications_event_recipient"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_notifications_workspace",
        ),
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = _id()
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    principal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("principals.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()
