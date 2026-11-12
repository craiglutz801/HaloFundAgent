"""Load the six fictional companies. Re-running is a no-op until reset-fixtures."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from uuid import UUID

from openpyxl import Workbook
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from halo.calculations.capacity import estimated_capacity_hours
from halo.db.models import (
    AgentAssignment,
    AgentRun,
    Artifact,
    CloseRecord,
    Company,
    Concern,
    Decision,
    Document,
    EvidenceRecord,
    EvidenceSnapshot,
    Finding,
    FindingEvidence,
    IcPacket,
    Initiative,
    InvestmentCase,
    MetricDefinition,
    MetricObservation,
    Notification,
    Organization,
    OrganizationMembership,
    Principal,
    Review,
    SnapshotEvidence,
    StageEvent,
    ValueEntry,
    Workspace,
    WorkspaceMembership,
)
from halo.db.session import open_migration_session
from halo.domain.lifecycle import assignment_status_for_run, from_case_status
from halo.evidence.store import LocalObjectStore, clear_fixture_root
from halo.models.schemas import Finding as FindingModel
from halo.models.schemas import LensAssessment, XavierScorecard
from halo.settings import Settings, get_settings
from halo.util import canonical_json, canonical_sha256, fid

POLICY = "2026-10-06"
NOW = datetime.now(timezone.utc)

PARTNER = [
    "workspace.read",
    "evidence.upload",
    "run.create",
    "artifact.review",
    "concern.disposition",
    "case.submit_ic",
    "ic.decide",
]
DEAL = [
    "workspace.read",
    "evidence.upload",
    "run.create",
    "artifact.review",
    "concern.disposition",
    "case.submit_ic",
]
PLATFORM = ["workspace.read", "evidence.upload", "initiative.approve"]
OPERATING = ["workspace.read", "initiative.approve", "playbook.publish"]
BOARD = ["workspace.read", "artifact.review"]
CFO = ["workspace.read", "artifact.review", "value.verify", "report.release"]
ADMIN = ["admin.manage", "workspace.read"]
ANALYST = ["workspace.read", "evidence.upload", "artifact.review"]


def seed(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    store = LocalObjectStore(settings.object_root_path)
    with open_migration_session() as db:
        existing = db.scalar(select(func.count()).select_from(Organization))
    if not existing:
        clear_fixture_root(settings.object_root_path)
        with open_migration_session() as db:
            if db.scalar(select(func.count()).select_from(Organization)):
                return False
            _load(db, store)
            _load_book(db, store)
            apply_company_profiles(db)
            db.commit()
        return True
    with open_migration_session() as db:
        added = _load_book(db, store)
        profiles = apply_company_profiles(db)
        db.commit()
    return added > 0 or profiles > 0


def apply_company_profiles(db: Session) -> int:
    """Write the business snapshot onto the company. A process does not own it."""
    from halo.services.company_profiles import PROFILES

    updated = 0
    for company in db.scalars(select(Company)).all():
        profile = PROFILES.get(company.display_name)
        if profile is None:
            continue
        changed = any(getattr(company, key) != value for key, value in profile.items())
        if not changed:
            continue
        for key, value in profile.items():
            setattr(company, key, value)
        updated += 1
    return updated


def database_has_live_organization(db: Session) -> bool:
    modes = db.scalars(select(Organization.mode)).all()
    return any(mode != "fixture" for mode in modes)


def _load(db: Session, store: LocalObjectStore) -> None:
    org_id = fid("org")
    db.add(
        Organization(
            id=org_id,
            name="Halo Fund",
            policy_version=POLICY,
            mode="fixture",
        )
    )
    people = {
        "jordan.hale": ("Jordan Hale", "partner", PARTNER),
        "priya.shah": ("Priya Shah", "deal_lead", DEAL),
        "alex.chen": ("Alex Chen", "platform_lead", PLATFORM),
        "morgan.ellis": ("Morgan Ellis", "operating_partner", OPERATING),
        "sam.okonkwo": ("Sam Okonkwo", "board", BOARD),
        "riley.quinn": ("Riley Quinn", "cfo", CFO),
        "avery.brooks": ("Avery Brooks", "administrator", ADMIN),
        "blake.iverson": ("Blake Iverson", "analyst", ANALYST),
    }
    for subject, (name, _role, _caps) in people.items():
        db.add(
            Principal(
                id=fid("principal", subject),
                kind="user",
                oidc_subject=f"fixture:{subject}",
                display_name=name,
                email=f"{subject}@halo.example",
                active=True,
            )
        )
    db.flush()
    for subject, (_name, role, _caps) in people.items():
        db.add(
            OrganizationMembership(
                id=fid("orgmem", subject),
                organization_id=org_id,
                principal_id=fid("principal", subject),
                role=role,
                status="active",
            )
        )
    fund_id = fid("workspace", "fund")
    db.add(
        Workspace(
            id=fund_id,
            organization_id=org_id,
            kind="fund",
            company_id=None,
            classification="internal",
            status="active",
            name="Halo Fund",
        )
    )
    db.flush()
    company_slugs = ["atlas", "vela", "rally", "court", "sideline", "northline"]
    for slug in company_slugs:
        db.add(
            Workspace(
                id=fid("workspace", slug),
                organization_id=org_id,
                kind="company",
                company_id=None,
                classification="company",
                status="active",
                name=slug.title(),
            )
        )
    db.flush()

    access = {
        "jordan.hale": ["fund", *company_slugs],
        "priya.shah": ["fund", "atlas", "vela", "sideline", "northline"],
        "alex.chen": ["fund", "rally"],
        "morgan.ellis": ["fund", "rally", "court"],
        "sam.okonkwo": ["rally", "court"],
        "riley.quinn": ["fund", "atlas", "vela", "rally", "court", "sideline", "northline"],
        "avery.brooks": ["fund", *company_slugs],
        "blake.iverson": ["vela"],
    }
    for subject, slugs in access.items():
        caps = people[subject][2]
        role = people[subject][1]
        for slug in slugs:
            db.add(
                WorkspaceMembership(
                    id=fid("wsmem", subject, slug),
                    organization_id=org_id,
                    workspace_id=fid("workspace", slug),
                    principal_id=fid("principal", subject),
                    role=role,
                    capabilities=caps,
                    status="active",
                )
            )
    db.flush()

    ctx = _Ctx(db, store, org_id)
    _company_northline(ctx)
    _company_sideline(ctx)
    _company_atlas(ctx)
    _company_vela(ctx)
    _company_rally(ctx)
    _company_court(ctx)
    for slug in company_slugs:
        ctx.db.execute(
            text(
                "UPDATE workspaces SET company_id = :company "
                "WHERE id = :workspace AND organization_id = :org"
            ),
            {
                "company": fid("company", slug),
                "workspace": fid("workspace", slug),
                "org": org_id,
            },
        )


class _Ctx:
    def __init__(self, db: Session, store: LocalObjectStore, org_id: UUID) -> None:
        self.db = db
        self.store = store
        self.org_id = org_id
        self._assignments: set[UUID] = set()

    def ws(self, slug: str) -> UUID:
        return fid("workspace", slug)

    def company(
        self,
        slug: str,
        *,
        legal_name: str,
        website: str,
        stage: str,
        owner: str,
        display_name: str | None = None,
    ) -> Company:
        row = Company(
            id=fid("company", slug),
            organization_id=self.org_id,
            workspace_id=self.ws(slug),
            legal_name=legal_name,
            display_name=display_name or slug.title(),
            website=website,
            stage=stage,
            owner_id=fid("principal", owner),
            row_version=1,
        )
        self.db.add(row)
        return row

    def case(
        self,
        slug: str,
        case_key: str,
        *,
        case_type: str,
        status: str,
        owner: str,
        due_at: datetime | None,
    ) -> InvestmentCase:
        phase, outcome, on_hold = from_case_status(status)
        if status == "open":
            company = self.db.get(Company, fid("company", slug))
            if company is not None:
                phase, outcome, on_hold = from_case_status(company.stage)
        row = InvestmentCase(
            id=fid("case", slug, case_key),
            organization_id=self.org_id,
            workspace_id=self.ws(slug),
            company_id=fid("company", slug),
            case_type=case_type,
            status=status,
            owner_id=fid("principal", owner),
            due_at=due_at,
            policy_version=POLICY,
            phase=phase,
            outcome=outcome,
            on_hold=on_hold,
            phase_entered_at=NOW,
            outcome_at=NOW if outcome != "open" else None,
            row_version=1,
        )
        self.db.add(row)
        return row

    def event(
        self,
        slug: str,
        key: str,
        *,
        case_key: str,
        from_stage: str,
        to_stage: str,
        reason: str,
        actor: str,
        when: datetime,
    ) -> None:
        self.db.add(
            StageEvent(
                id=fid("stage", slug, key),
                organization_id=self.org_id,
                workspace_id=self.ws(slug),
                company_id=fid("company", slug),
                case_id=fid("case", slug, case_key),
                from_stage=from_stage,
                to_stage=to_stage,
                reason=reason,
                actor_id=fid("principal", actor),
                source_kind="fixture_history",
                source_id=None,
                created_at=when,
            )
        )

    def document(
        self,
        slug: str,
        key: str,
        *,
        filename: str,
        mime: str,
        data: bytes,
        source_kind: str,
        origin_class: str,
        usage_policy: str = "diligence",
        ingestion_status: str = "ready",
        classification: str = "confidential",
    ) -> Document:
        digest = canonical_sha256({"filename": filename, "sha": data.hex()})
        # Hash the bytes themselves. The helper above is not the document hash.
        from halo.util import sha256_hex

        digest = sha256_hex(data)
        object_key = f"fixture/{slug}/documents/{key}"
        self.store.put_immutable(object_key, data, digest)
        row = Document(
            id=fid("document", slug, key),
            organization_id=self.org_id,
            workspace_id=self.ws(slug),
            logical_doc_id=fid("logical", slug, key),
            object_key=object_key,
            sha256=digest,
            version=1,
            mime=mime,
            size=len(data),
            filename=filename,
            classification=classification,
            source_kind=source_kind,
            usage_policy=usage_policy,
            ingestion_status=ingestion_status,
            origin_class=origin_class,
        )
        self.db.add(row)
        return row

    def evidence(
        self,
        slug: str,
        key: str,
        *,
        document_key: str,
        kind: str,
        locator: dict,
        excerpt: str,
        origin_class: str,
        sample_size: str = "",
        limitations: list | None = None,
        observed_start: datetime | None = None,
        observed_end: datetime | None = None,
        collected_at: datetime | None = None,
    ) -> EvidenceRecord:
        row = EvidenceRecord(
            id=fid("evidence", slug, key),
            organization_id=self.org_id,
            workspace_id=self.ws(slug),
            document_id=fid("document", slug, document_key),
            kind=kind,
            locator_json=locator,
            excerpt=excerpt,
            observed_start=observed_start,
            observed_end=observed_end,
            collected_at=collected_at,
            sample_size=sample_size,
            independence_group=f"{slug}:{key}",
            status="active",
            origin_class=origin_class,
            limitations=limitations or [],
        )
        self.db.add(row)
        return row

    def run(
        self,
        slug: str,
        agent: str,
        *,
        case_key: str,
        phase: str,
        status: str,
        owner: str,
        detail: str = "",
        title: str | None = None,
    ) -> AgentRun:
        assignment_id = fid("assignment", slug, case_key, agent)
        if (
            assignment_id not in self._assignments
            and self.db.get(AgentAssignment, assignment_id) is None
        ):
            project_status = assignment_status_for_run(status)
            self.db.add(
                AgentAssignment(
                    id=assignment_id,
                    organization_id=self.org_id,
                    workspace_id=self.ws(slug),
                    company_id=fid("company", slug),
                    agent_id=agent,
                    investment_process_id=fid("case", slug, case_key),
                    title=title or f"{agent.title()} project",
                    objective=detail or "Specialist project for this process",
                    status=project_status,
                    owner_id=fid("principal", owner),
                    created_by=fid("principal", owner),
                    started_at=None if project_status == "queued" else NOW,
                    completed_at=NOW if project_status == "completed" else None,
                    last_activity_at=NOW,
                    blocked_reason="A run failed. The project stays open for retry."
                    if project_status == "blocked"
                    else "",
                    agent_config_version="v1",
                )
            )
            self._assignments.add(assignment_id)
        row = AgentRun(
            id=fid("run", slug, case_key, agent, phase),
            organization_id=self.org_id,
            workspace_id=self.ws(slug),
            case_id=fid("case", slug, case_key),
            assignment_id=assignment_id,
            agent_name=agent,
            phase=phase,
            snapshot_id=fid("snapshot", slug, case_key) if status != "queued" else None,
            workflow_id=f"fixture/{slug}/{case_key}/{agent}/{phase}",
            status=status,
            owner_id=fid("principal", owner),
            prompt_version="v1",
            schema_version="v1",
            provider="fake",
            model="fixture",
            config_hash="fixture",
            status_detail=detail,
            heartbeat_at=NOW if status == "running" else None,
        )
        self.db.add(row)
        return row

    def artifact(
        self,
        slug: str,
        key: str,
        *,
        case_key: str,
        agent: str,
        phase: str,
        kind: str,
        content: dict,
        status: str,
        sealed: bool = False,
    ) -> Artifact:
        raw = canonical_json(content)
        from halo.util import sha256_hex

        digest = sha256_hex(raw)
        object_key = f"fixture/{slug}/artifacts/{key}.json"
        self.store.put_immutable(object_key, raw, digest)
        when = NOW - timedelta(days=2)
        row = Artifact(
            id=fid("artifact", slug, key),
            organization_id=self.org_id,
            workspace_id=self.ws(slug),
            run_id=fid("run", slug, case_key, agent, phase),
            phase=phase,
            kind=kind,
            version=1,
            object_key=object_key,
            sha256=digest,
            status=status,
            content_json=content,
            generated_at=when,
            published_at=when if status in {"validated", "reviewed", "sealed"} else None,
            sealed_at=when if sealed else None,
        )
        self.db.add(row)
        return row

    def review(self, slug: str, artifact_key: str, *, reviewer: str, notes: str) -> None:
        artifact = self.db.get(Artifact, fid("artifact", slug, artifact_key))
        assert artifact is not None
        self.db.add(
            Review(
                id=fid("review", slug, artifact_key),
                organization_id=self.org_id,
                workspace_id=self.ws(slug),
                artifact_id=artifact.id,
                artifact_sha256=artifact.sha256,
                reviewer_id=fid("principal", reviewer),
                verdict="approve_draft",
                notes=notes,
                reviewed_at=NOW - timedelta(days=1),
            )
        )

    def snapshot(self, slug: str, case_key: str, evidence_keys: list[str]) -> EvidenceSnapshot:
        manifest = {
            "case_id": str(fid("case", slug, case_key)),
            "evidence": [
                {
                    "id": str(fid("evidence", slug, key)),
                    "document_id": str(self._evidence_document(slug, key)),
                }
                for key in evidence_keys
            ],
            "policy_version": POLICY,
        }
        raw = canonical_json(manifest)
        from halo.util import sha256_hex

        digest = sha256_hex(raw)
        object_key = f"fixture/{slug}/snapshots/{case_key}.json"
        self.store.put_immutable(object_key, raw, digest)
        row = EvidenceSnapshot(
            id=fid("snapshot", slug, case_key),
            organization_id=self.org_id,
            workspace_id=self.ws(slug),
            case_id=fid("case", slug, case_key),
            manifest_key=object_key,
            manifest_sha256=digest,
            frozen_at=NOW - timedelta(days=3),
            status="frozen",
        )
        self.db.add(row)
        for key in evidence_keys:
            self.db.add(
                SnapshotEvidence(
                    snapshot_id=row.id,
                    evidence_id=fid("evidence", slug, key),
                    organization_id=self.org_id,
                    workspace_id=self.ws(slug),
                )
            )
        return row

    def _evidence_document(self, slug: str, evidence_key: str) -> UUID:
        evidence = self.db.get(EvidenceRecord, fid("evidence", slug, evidence_key))
        assert evidence is not None
        return evidence.document_id

    def packet(
        self,
        slug: str,
        case_key: str,
        *,
        artifact_keys: list[str],
        status: str,
    ) -> IcPacket:
        artifacts = [self.db.get(Artifact, fid("artifact", slug, key)) for key in artifact_keys]
        manifest = {
            "case_id": str(fid("case", slug, case_key)),
            "policy_version": POLICY,
            "artifacts": [
                {
                    "id": str(item.id),
                    "kind": item.kind,
                    "sha256": item.sha256,
                    "version": item.version,
                }
                for item in artifacts
                if item is not None
            ],
        }
        raw = canonical_json(manifest)
        from halo.util import sha256_hex

        digest = sha256_hex(raw)
        object_key = f"fixture/{slug}/packets/{case_key}.json"
        self.store.put_immutable(object_key, raw, digest)
        row = IcPacket(
            id=fid("packet", slug, case_key),
            organization_id=self.org_id,
            workspace_id=self.ws(slug),
            case_id=fid("case", slug, case_key),
            version=1,
            snapshot_id=fid("snapshot", slug, case_key),
            manifest_key=object_key,
            manifest_sha256=digest,
            policy_version=POLICY,
            status=status,
            artifact_ids=[item.id for item in artifacts if item is not None],
        )
        self.db.add(row)
        return row


def _finding(
    statement: str, *, kind: str, evidence: list[str], slug: str, materiality: str = "material"
) -> dict:
    model = FindingModel(
        statement=statement,
        kind=kind,  # type: ignore[arg-type]
        materiality=materiality,  # type: ignore[arg-type]
        evidence_ids=[fid("evidence", slug, key) for key in evidence],
        confidence="medium" if evidence else "insufficient",
        confidence_reason="Tied to the frozen fixture snapshot."
        if evidence
        else "Evidence is missing.",
        limitations=["Fixture source. Not a live company."],
        validation_question=None if evidence else "What source would resolve this?",
    )
    return model.model_dump(mode="json")


def _load_book(db: Session, store: LocalObjectStore) -> int:
    """Add fictional companies that are not already in this fixture database."""
    from halo.services.fixture_book import BOOK

    org = db.scalar(select(Organization).where(Organization.mode == "fixture"))
    if org is None:
        return 0
    roles = {
        "jordan.hale": ("partner", PARTNER),
        "priya.shah": ("deal_lead", DEAL),
        "morgan.ellis": ("operating_partner", OPERATING),
        "riley.quinn": ("cfo", CFO),
        "avery.brooks": ("administrator", ADMIN),
    }
    ctx = _Ctx(db, store, org.id)
    added = 0
    for spec in BOOK:
        slug = spec["slug"]
        if db.get(Company, fid("company", slug)) is not None:
            continue
        workspace_id = fid("workspace", slug)
        if db.get(Workspace, workspace_id) is None:
            db.add(
                Workspace(
                    id=workspace_id,
                    organization_id=org.id,
                    kind="company",
                    company_id=None,
                    classification="company",
                    status="active",
                    name=spec["display_name"],
                )
            )
            db.flush()
        for subject in dict.fromkeys(spec["readers"]):
            role, caps = roles[subject]
            membership_id = fid("wsmem", subject, slug)
            if db.get(WorkspaceMembership, membership_id) is None:
                db.add(
                    WorkspaceMembership(
                        id=membership_id,
                        organization_id=org.id,
                        workspace_id=workspace_id,
                        principal_id=fid("principal", subject),
                        role=role,
                        capabilities=caps,
                        status="active",
                    )
                )
        db.flush()
        ctx.company(
            slug,
            legal_name=spec["legal_name"],
            website=spec["website"],
            stage=spec["stage"],
            owner=spec["owner"],
            display_name=spec["display_name"],
        )
        ctx.case(
            slug,
            "initial",
            case_type="initial",
            status=spec["case_status"],
            owner=spec["owner"],
            due_at=NOW + timedelta(days=21),
        )
        db.flush()
        memo = spec["memo"].encode()
        ctx.document(
            slug,
            "memo",
            filename=f"{slug}-memo.txt",
            mime="text/plain",
            data=memo,
            source_kind="partner_note",
            origin_class="raw_company_source",
        )
        ctx.evidence(
            slug,
            "memo",
            document_key="memo",
            kind="partner_note",
            locator={"kind": "text", "section": "memo"},
            excerpt=spec["memo"],
            origin_class="raw_company_source",
        )
        db.flush()
        for job in spec["agents"]:
            ctx.run(
                slug,
                job["agent"],
                case_key="initial",
                phase=job["phase"],
                status=job["status"],
                owner=spec["owner"],
                detail=job["detail"],
                title=job["title"],
            )
            db.flush()
            if job["status"] == "queued":
                continue
            ctx.artifact(
                slug,
                f"{job['agent']}-{job['kind']}",
                case_key="initial",
                agent=job["agent"],
                phase=job["phase"],
                kind=job["kind"],
                content=job["content"],
                status=job["artifact_status"],
            )
        db.flush()
        db.execute(
            text(
                "UPDATE workspaces SET company_id = :company "
                "WHERE id = :workspace AND organization_id = :org"
            ),
            {"company": fid("company", slug), "workspace": workspace_id, "org": org.id},
        )
        added += 1
    return added


def _company_northline(ctx: _Ctx) -> None:
    ctx.company(
        "northline",
        legal_name="Northline Logistics, Inc.",
        website="https://northline.example",
        stage="discovered",
        owner="jordan.hale",
    )
    ctx.case(
        "northline", "initial", case_type="initial", status="open", owner="jordan.hale", due_at=None
    )
    ctx.db.flush()
    ctx.event(
        "northline",
        "discovered",
        case_key="initial",
        from_stage="discovered",
        to_stage="discovered",
        reason="Scout recorded a public sourcing profile. No meeting is approved.",
        actor="jordan.hale",
        when=NOW - timedelta(days=6),
    )
    ctx.document(
        "northline",
        "profile",
        filename="northline-public-profile.txt",
        mime="text/plain",
        data=b"Public profile fixture: Northline operates regional freight software. No revenue figure is included.",
        source_kind="public_profile",
        origin_class="raw_public_source",
        usage_policy="sourcing",
        classification="public",
    )
    ctx.evidence(
        "northline",
        "profile",
        document_key="profile",
        kind="company_profile",
        locator={"kind": "text", "paragraph": 1},
        excerpt="Public profile fixture: Northline operates regional freight software. No revenue figure is included.",
        origin_class="raw_public_source",
        collected_at=datetime(2026, 9, 12, tzinfo=timezone.utc),
    )
    ctx.db.flush()
    ctx.snapshot("northline", "initial", ["profile"])
    ctx.run(
        "northline",
        "scout",
        case_key="initial",
        phase="sourcing",
        status="ready_for_review",
        owner="jordan.hale",
    )
    ctx.db.flush()
    ctx.artifact(
        "northline",
        "scout",
        case_key="initial",
        agent="scout",
        phase="sourcing",
        kind="scout_shortlist",
        status="validated",
        content={
            "summary": "Northline matches a freight-software theme. Growth evidence is missing, so it is not ranked as a full-confidence fit.",
            "rubric_version": POLICY,
            "dimensions": {
                "stage": 2,
                "platform_specificity": 2,
                "growth_evidence": None,
                "experience_opportunity": 1,
                "playbook_fit": None,
            },
            "gaps": ["No audited or company-reported growth metric is in the snapshot."],
            "suggested_human_next_step": "Partner decides whether to accept a first look.",
        },
    )


def _company_sideline(ctx: _Ctx) -> None:
    ctx.company(
        "sideline",
        legal_name="Sideline Community, Inc.",
        website="https://sideline.example",
        stage="first_look",
        owner="priya.shah",
    )
    ctx.case(
        "sideline",
        "initial",
        case_type="initial",
        status="first_look",
        owner="priya.shah",
        due_at=NOW + timedelta(days=9),
    )
    ctx.db.flush()
    ctx.event(
        "sideline",
        "first-look",
        case_key="initial",
        from_stage="discovered",
        to_stage="first_look",
        reason="Partner accepted a first look on the public community profile.",
        actor="jordan.hale",
        when=NOW - timedelta(days=4),
    )
    ctx.document(
        "sideline",
        "profile",
        filename="sideline-first-look.txt",
        mime="text/plain",
        data=b"First-look note: Sideline runs a community product for amateur clubs. Revenue is not in this snapshot.",
        source_kind="human_note",
        origin_class="human_reference",
        usage_policy="sourcing",
    )
    ctx.evidence(
        "sideline",
        "profile",
        document_key="profile",
        kind="first_look_note",
        locator={"kind": "text", "paragraph": 1},
        excerpt="Sideline runs a community product for amateur clubs. Revenue is not in this snapshot.",
        origin_class="human_reference",
        collected_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
    )


def _company_atlas(ctx: _Ctx) -> None:
    ctx.company(
        "atlas",
        legal_name="Atlas Workflow Systems, Inc.",
        website="https://atlas.example",
        stage="diligence",
        owner="priya.shah",
    )
    ctx.case(
        "atlas",
        "initial",
        case_type="initial",
        status="diligence",
        owner="priya.shah",
        due_at=NOW + timedelta(days=12),
    )
    ctx.db.flush()
    ctx.event(
        "atlas",
        "diligence",
        case_key="initial",
        from_stage="first_look",
        to_stage="diligence",
        reason="Deal lead opened diligence on the frozen raw snapshot.",
        actor="priya.shah",
        when=NOW - timedelta(days=8),
    )
    workbook = _atlas_workbook()
    ctx.document(
        "atlas",
        "cohort",
        filename="atlas-cohort-retention.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        data=workbook,
        source_kind="workbook",
        origin_class="raw_company_source",
    )
    board = (
        "Board deck page 14 capture. The slide states gross retention of 92% "
        "and does not say whether that figure is logo retention or dollar retention, "
        "or whether contraction and reactivation are included."
    ).encode()
    ctx.document(
        "atlas",
        "board",
        filename="atlas-board-page-14.txt",
        mime="text/plain",
        data=board,
        source_kind="board_deck",
        origin_class="raw_company_source",
    )
    references = (
        "Three customer references supplied by the company, all introduced by the founder. "
        "The notes describe implementation speed. They are not an employee sample."
    ).encode()
    ctx.document(
        "atlas",
        "references",
        filename="atlas-reference-notes.txt",
        mime="text/plain",
        data=references,
        source_kind="reference_notes",
        origin_class="raw_company_source",
    )
    ctx.evidence(
        "atlas",
        "cohort",
        document_key="cohort",
        kind="cohort_table",
        locator={"kind": "sheet_cells", "sheet": "Cohort Retention", "cells": "D14:D20"},
        excerpt=(
            "Jan–Mar 2025 cohort. Dollar GRR is 84.1% after contraction and churn. "
            "Logo GRR on the same rows is 91.6%. Reactivation is excluded. "
            "Cells D14:D20 on sheet Cohort Retention."
        ),
        origin_class="raw_company_source",
        sample_size="Jan–Mar 2025 cohort",
        observed_start=datetime(2025, 1, 1, tzinfo=timezone.utc),
        observed_end=datetime(2025, 3, 31, tzinfo=timezone.utc),
        collected_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
        limitations=["Workbook extract does not include customer-level concentration."],
    )
    ctx.evidence(
        "atlas",
        "board",
        document_key="board",
        kind="board_claim",
        locator={"kind": "pdf_page", "page": 14, "label": "Q2 retention bridge"},
        excerpt=(
            "Page 14 states gross retention of 92% without defining logo versus dollar retention "
            "or the treatment of contraction."
        ),
        origin_class="raw_company_source",
        sample_size="single slide",
        observed_start=datetime(2025, 4, 1, tzinfo=timezone.utc),
        observed_end=datetime(2025, 6, 30, tzinfo=timezone.utc),
        collected_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
        limitations=["Definition is not stated on the slide."],
    )
    ctx.evidence(
        "atlas",
        "references",
        document_key="references",
        kind="reference_note",
        locator={"kind": "text", "section": "references"},
        excerpt="Three founder-introduced references describe implementation speed. No employee evidence is included.",
        origin_class="raw_company_source",
        sample_size="3 founder-introduced references",
        collected_at=datetime(2026, 6, 18, tzinfo=timezone.utc),
        limitations=["Selected by the company. Not an independent employee sample."],
    )
    ctx.db.flush()
    ctx.snapshot("atlas", "initial", ["cohort", "board", "references"])
    ctx.run(
        "atlas",
        "ainge",
        case_key="initial",
        phase="independent",
        status="ready_for_review",
        owner="priya.shah",
        detail="Retention definitions conflict. Concentration is unknown.",
    )
    ctx.run(
        "atlas",
        "xavier",
        case_key="initial",
        phase="independent",
        status="reviewed",
        owner="priya.shah",
        detail="EX and BX remain unscored. The first pass is finished.",
    )
    ctx.db.add(
        AgentAssignment(
            id=fid("assignment", "atlas", "initial", "mutombo", "references"),
            organization_id=ctx.org_id,
            workspace_id=ctx.ws("atlas"),
            company_id=fid("company", "atlas"),
            agent_id="mutombo",
            investment_process_id=fid("case", "atlas", "initial"),
            title="Reference challenge",
            objective="Test founder-introduced references as its own project. This does not open comparison grants.",
            status="active",
            owner_id=fid("principal", "priya.shah"),
            created_by=fid("principal", "priya.shah"),
            started_at=NOW,
            last_activity_at=NOW,
            agent_config_version="v1",
        )
    )
    ctx.run(
        "atlas",
        "mutombo",
        case_key="initial",
        phase="independent",
        status="running",
        owner="priya.shah",
        detail="Independent first pass is not sealed. Comparison grants are closed.",
    )
    ctx.db.flush()
    retention_statement = (
        "The cohort workbook computes dollar GRR of 84.1% for Jan–Mar 2025, "
        "while page 14 states 92% without a definition."
    )
    ainge = {
        "summary": "Dollar retention and the board slide do not use the same definition. Customer concentration is unknown.",
        "findings": [
            _finding(
                retention_statement,
                kind="observation",
                evidence=["cohort", "board"],
                slug="atlas",
            )
        ],
        "missing_evidence": ["Customer concentration is not in the snapshot."],
        "human_questions": ["Which retention definition should the memo use?"],
        "proposed_actions": ["Deal lead reconciles the retention definition before IC."],
        "limitations": ["No blended retention number is reported."],
        "return_model": {
            "status": "unavailable",
            "reason": "Concentration and a consistent retention definition are missing.",
        },
    }
    ctx.artifact(
        "atlas",
        "ainge",
        case_key="initial",
        agent="ainge",
        phase="independent",
        kind="ainge_report",
        status="validated",
        content=ainge,
    )
    xavier = XavierScorecard(
        summary="Reference notes support a limited customer observation. Employee and brand lenses are unscored.",
        findings=[
            FindingModel(
                statement="The reference notes are three founder-introduced conversations about implementation speed.",
                kind="observation",
                materiality="supporting",
                evidence_ids=[fid("evidence", "atlas", "references")],
                confidence="low",
                confidence_reason="The sample was selected by the company.",
                limitations=["Not a population benchmark."],
                validation_question=None,
            )
        ],
        missing_evidence=["No employee evidence.", "No authorized brand evidence."],
        human_questions=["Can the deal lead obtain an employee source the company did not select?"],
        proposed_actions=["Keep EX and BX unscored until evidence exists."],
        limitations=["There is no overall experience score."],
        lenses=[
            LensAssessment(
                lens="CX",
                score=3,
                status="assessed",
                confidence="low",
                confidence_reason="Company-selected references only.",
                evidence_ids=[fid("evidence", "atlas", "references")],
                sample_summary="3 founder-introduced references",
                observed_period="2026-06",
                limitations=["Selected sample."],
                rubric_criterion="referenced customer implementation evidence",
            ),
            LensAssessment(
                lens="EX",
                score=None,
                status="insufficient_evidence",
                confidence="insufficient",
                confidence_reason="No employee source is in the snapshot.",
                evidence_ids=[],
                sample_summary="none",
                observed_period=None,
                limitations=["Absence is not a score of zero."],
                rubric_criterion=None,
            ),
            LensAssessment(
                lens="BX",
                score=None,
                status="insufficient_evidence",
                confidence="insufficient",
                confidence_reason="No authorized perception evidence is in the snapshot.",
                evidence_ids=[],
                sample_summary="none",
                observed_period=None,
                limitations=["Absence is not a score of zero."],
                rubric_criterion=None,
            ),
            LensAssessment(
                lens="PX",
                score=3,
                status="assessed",
                confidence="low",
                confidence_reason="A company walkthrough note is not a population benchmark.",
                evidence_ids=[fid("evidence", "atlas", "references")],
                sample_summary="reference notes mention the product flow",
                observed_period="2026-06",
                limitations=["Not an independent walkthrough."],
                rubric_criterion="documented product walkthrough",
            ),
        ],
        claim_gaps=[
            {
                "company_claim_ref": "board-page-14-retention",
                "status": "untested",
                "rationale": "The slide's 92% claim is a financial definition issue, not an experience score.",
            }
        ],
    )
    ctx.artifact(
        "atlas",
        "xavier",
        case_key="initial",
        agent="xavier",
        phase="independent",
        kind="xavier_scorecard",
        status="validated",
        content=xavier.model_dump(mode="json"),
    )
    ctx.db.flush()
    artifact = ctx.db.get(Artifact, fid("artifact", "atlas", "ainge"))
    assert artifact is not None
    ctx.db.add(
        Finding(
            id=fid("finding", "atlas", "retention"),
            organization_id=ctx.org_id,
            workspace_id=ctx.ws("atlas"),
            artifact_id=artifact.id,
            statement=retention_statement,
            kind="observation",
            materiality="material",
            confidence="medium",
            limitations=["The two sources use different language and are not averaged."],
            validation_question="Which definition is the company prepared to stand behind?",
        )
    )
    ctx.db.flush()
    for key, relationship in (("cohort", "support"), ("board", "contradict")):
        ctx.db.add(
            FindingEvidence(
                finding_id=fid("finding", "atlas", "retention"),
                evidence_id=fid("evidence", "atlas", key),
                organization_id=ctx.org_id,
                workspace_id=ctx.ws("atlas"),
                relationship=relationship,
            )
        )
    ctx.db.add(
        Concern(
            id=fid("concern", "atlas", "retention"),
            organization_id=ctx.org_id,
            workspace_id=ctx.ws("atlas"),
            case_id=fid("case", "atlas", "initial"),
            artifact_id=artifact.id,
            severity="material",
            blocking=True,
            status="open",
            owner_id=fid("principal", "priya.shah"),
            question="Reconcile retention definitions",
            due_at=NOW + timedelta(days=6),
            row_version=1,
        )
    )
    ctx.db.add(
        Concern(
            id=fid("concern", "atlas", "concentration"),
            organization_id=ctx.org_id,
            workspace_id=ctx.ws("atlas"),
            case_id=fid("case", "atlas", "initial"),
            artifact_id=artifact.id,
            severity="material",
            blocking=True,
            status="open",
            owner_id=fid("principal", "priya.shah"),
            question="Obtain customer concentration evidence",
            due_at=NOW + timedelta(days=6),
            row_version=1,
        )
    )


def _company_vela(ctx: _Ctx) -> None:
    ctx.company(
        "vela",
        legal_name="Vela Health Scheduling, Inc.",
        website="https://vela.example",
        stage="ic_review",
        owner="priya.shah",
    )
    ctx.case(
        "vela",
        "initial",
        case_type="initial",
        status="ic_review",
        owner="priya.shah",
        due_at=NOW + timedelta(days=2),
    )
    ctx.db.flush()
    ctx.event(
        "vela",
        "ic",
        case_key="initial",
        from_stage="diligence",
        to_stage="ic_review",
        reason="Deal lead submitted the frozen packet after reviews.",
        actor="priya.shah",
        when=NOW - timedelta(days=1),
    )
    ctx.document(
        "vela",
        "memo-sources",
        filename="vela-customer-and-terms.txt",
        mime="text/plain",
        data=(
            b"Two health systems are 71% of reported ARR. "
            b"Customer references describe scheduling adoption. "
            b"This fixture is not a forecast."
        ),
        source_kind="diligence_binder",
        origin_class="raw_company_source",
    )
    ctx.evidence(
        "vela",
        "concentration",
        document_key="memo-sources",
        kind="arr_concentration",
        locator={"kind": "text", "section": "concentration"},
        excerpt="Two health systems are 71% of reported ARR in the company binder.",
        origin_class="raw_company_source",
        sample_size="company-reported ARR",
        collected_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        limitations=["Company-reported. Not a fund-admin figure."],
    )
    ctx.evidence(
        "vela",
        "references",
        document_key="memo-sources",
        kind="reference_note",
        locator={"kind": "text", "section": "references"},
        excerpt="Customer references describe scheduling adoption in two health systems.",
        origin_class="raw_company_source",
        sample_size="company-introduced references",
        collected_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    ctx.db.flush()
    ctx.snapshot("vela", "initial", ["concentration", "references"])
    for agent, phase, status in (
        ("ainge", "independent", "reviewed"),
        ("xavier", "independent", "reviewed"),
        ("mutombo", "independent", "reviewed"),
        ("mutombo", "comparison", "reviewed"),
        ("stockton", "pre_close", "reviewed"),
    ):
        ctx.run("vela", agent, case_key="initial", phase=phase, status=status, owner="priya.shah")
    ctx.db.flush()
    scenario = {
        "label": "Illustrative gross company math, not a Halo forecast",
        "entry_check": "20000000",
        "post_money": "200000000",
        "initial_ownership": "0.10",
        "modeled_dilution": "0.20",
        "diluted_ownership": "0.08",
        "cases": [
            {"exit_equity": "250000000", "gross_proceeds": "20000000", "gross_moic": "1.00"},
            {"exit_equity": "625000000", "gross_proceeds": "50000000", "gross_moic": "2.50"},
            {"exit_equity": "1000000000", "gross_proceeds": "80000000", "gross_moic": "4.00"},
        ],
        "irr": None,
        "irr_reason": "IRR is unavailable because this illustration has no cash-flow dates.",
        "net_return": None,
        "limitations": [
            "Assumes no preference stack and no additional invested capital.",
            "Gross company MOIC is not a net fund return.",
        ],
    }
    ctx.artifact(
        "vela",
        "ainge",
        case_key="initial",
        agent="ainge",
        phase="independent",
        kind="ainge_report",
        status="reviewed",
        content={
            "summary": "The case depends on two health systems. The illustrative return math is gross company MOIC only.",
            "findings": [
                _finding(
                    "The binder reports that two health systems are 71% of ARR.",
                    kind="company_claim",
                    evidence=["concentration"],
                    slug="vela",
                )
            ],
            "missing_evidence": [],
            "human_questions": ["What happens to the case if either health system does not renew?"],
            "proposed_actions": ["IC reads the dissent with the memo."],
            "limitations": ["Return cases are illustrations, not a forecast."],
            "scenario": scenario,
        },
    )
    ctx.artifact(
        "vela",
        "xavier",
        case_key="initial",
        agent="xavier",
        phase="independent",
        kind="xavier_scorecard",
        status="reviewed",
        content={
            "summary": "Customer references support a limited CX observation. EX is unscored.",
            "findings": [
                _finding(
                    "References describe scheduling adoption and were introduced by the company.",
                    kind="observation",
                    evidence=["references"],
                    slug="vela",
                    materiality="supporting",
                )
            ],
            "missing_evidence": ["No employee evidence."],
            "human_questions": [],
            "proposed_actions": [],
            "limitations": ["No overall experience score."],
            "lenses": [
                {
                    "lens": "CX",
                    "score": 4,
                    "status": "assessed",
                    "confidence": "medium",
                    "confidence_reason": "References agree on adoption and were company-introduced.",
                    "evidence_ids": [str(fid("evidence", "vela", "references"))],
                    "sample_summary": "company-introduced references",
                    "observed_period": "2026-08",
                    "limitations": ["Selected sample."],
                    "rubric_criterion": "customer adoption references",
                },
                {
                    "lens": "EX",
                    "score": None,
                    "status": "insufficient_evidence",
                    "confidence": "insufficient",
                    "confidence_reason": "No employee source.",
                    "evidence_ids": [],
                    "sample_summary": "none",
                    "observed_period": None,
                    "limitations": ["Unscored is not zero."],
                    "rubric_criterion": None,
                },
                {
                    "lens": "BX",
                    "score": 3,
                    "status": "assessed",
                    "confidence": "low",
                    "confidence_reason": "Only the company's own description of positioning is available.",
                    "evidence_ids": [str(fid("evidence", "vela", "references"))],
                    "sample_summary": "binder language",
                    "observed_period": "2026-08",
                    "limitations": ["No third-party perception study."],
                    "rubric_criterion": "positioning statement",
                },
                {
                    "lens": "PX",
                    "score": 3,
                    "status": "assessed",
                    "confidence": "low",
                    "confidence_reason": "Product description in the binder, not an independent walkthrough.",
                    "evidence_ids": [str(fid("evidence", "vela", "references"))],
                    "sample_summary": "binder",
                    "observed_period": "2026-08",
                    "limitations": ["No independent walkthrough."],
                    "rubric_criterion": "documented product description",
                },
            ],
            "claim_gaps": [],
        },
    )
    dissent = {
        "summary": "Independent bear case: renewal of either large health system is a material assumption.",
        "findings": [
            _finding(
                "If either of the two health systems does not renew, the base case changes. This is a hypothesis, not a predicted outcome.",
                kind="inference",
                evidence=["concentration"],
                slug="vela",
            )
        ],
        "missing_evidence": [],
        "human_questions": ["What contractual notice and term remain on each health system?"],
        "proposed_actions": ["Keep this bear case attached to the packet."],
        "limitations": ["Sealed independent pass. Later answers do not rewrite it."],
        "failure_scenarios": [
            "Loss of one health system removes a majority of reported ARR. This is not asserted as an outcome."
        ],
    }
    # The inference has evidence, so the validation question may be null. The finding helper sets it only when evidence is empty.
    ctx.artifact(
        "vela",
        "mutombo-independent",
        case_key="initial",
        agent="mutombo",
        phase="independent",
        kind="independent_risk_report",
        status="sealed",
        sealed=True,
        content=dissent,
    )
    ctx.artifact(
        "vela",
        "mutombo-comparison",
        case_key="initial",
        agent="mutombo",
        phase="comparison",
        kind="mutombo_review",
        status="reviewed",
        content={
            "summary": "Comparison agrees the concentration claim is company-reported and still material.",
            "findings": [],
            "missing_evidence": [],
            "human_questions": [
                "IC should read the sealed bear case, which this review does not replace."
            ],
            "proposed_actions": [],
            "limitations": ["The independent artifact remains the bear case of record."],
            "claim_checks": [
                {
                    "claim_ref": "two-health-systems-71-arr",
                    "verdict": "untested",
                    "rationale": "The figure is company-reported. It is not independently verified.",
                }
            ],
        },
    )
    ctx.artifact(
        "vela",
        "stockton",
        case_key="initial",
        agent="stockton",
        phase="pre_close",
        kind="activation_thesis",
        status="reviewed",
        content={
            "summary": "A pre-close activation hypothesis only. No inventory is booked.",
            "hypothesis": "Clinic operators may use a scheduling workshop if the company and the asset owner approve.",
            "available_assets": [],
            "unknown_assets": ["Workshop inventory is not confirmed."],
            "measurement": "Tagged attendance would be observed activity, not revenue.",
            "approval_needs": ["Company owner", "asset owner"],
            "findings": [],
            "missing_evidence": ["No approved asset."],
            "human_questions": [],
            "proposed_actions": ["Do not book inventory from this thesis."],
            "limitations": ["This is not an activation commitment."],
        },
    )
    ctx.db.flush()
    for key, note in (
        ("ainge", "Reviewed the gross scenario and the concentration claim."),
        ("xavier", "EX stays unscored. No overall score was requested."),
        ("mutombo-independent", "Sealed bear case reviewed without editing it."),
        ("mutombo-comparison", "Comparison does not replace the sealed dissent."),
        ("stockton", "Thesis does not book inventory."),
    ):
        ctx.review("vela", key, reviewer="priya.shah", notes=note)
    ctx.document(
        "vela",
        "closing",
        filename="vela-closing-record.txt",
        mime="text/plain",
        data=b"Fixture closing record for Vela Health Scheduling, Inc. It is verified and not yet used.",
        source_kind="closing",
        origin_class="human_reference",
        usage_policy="closing",
        ingestion_status="verified",
    )
    ctx.db.flush()
    ctx.packet(
        "vela",
        "initial",
        artifact_keys=["ainge", "xavier", "mutombo-independent", "mutombo-comparison", "stockton"],
        status="frozen",
    )


def _company_rally(ctx: _Ctx) -> None:
    ctx.company(
        "rally",
        legal_name="Rally Marketplace, Inc.",
        website="https://rally.example",
        stage="owned",
        owner="jordan.hale",
    )
    ctx.case(
        "rally", "initial", case_type="initial", status="owned", owner="jordan.hale", due_at=None
    )
    ctx.case(
        "rally",
        "follow-on",
        case_type="follow_on",
        status="ic_review",
        owner="jordan.hale",
        due_at=NOW + timedelta(days=5),
    )
    ctx.db.flush()
    ctx.event(
        "rally",
        "owned",
        case_key="initial",
        from_stage="closing",
        to_stage="owned",
        reason="Verified closing document recorded by an authorized person.",
        actor="jordan.hale",
        when=NOW - timedelta(days=40),
    )
    ctx.document(
        "rally",
        "closing",
        filename="rally-closing-record.txt",
        mime="text/plain",
        data=b"Fixture closing record for Rally Marketplace, Inc. Effective date is recorded by a human.",
        source_kind="closing",
        origin_class="human_reference",
        usage_policy="closing",
        ingestion_status="verified",
    )
    ctx.document(
        "rally",
        "meetings",
        filename="rally-tagged-meetings.csv",
        mime="text/csv",
        data=b"meeting_id,tagged,revenue\n1,true,\n2,true,\n",
        source_kind="campaign_export",
        origin_class="raw_company_source",
        usage_policy="portfolio",
    )
    ctx.document(
        "rally",
        "time-study",
        filename="rally-time-study.txt",
        mime="text/plain",
        data=(
            b"Support time study. Baseline 12 minutes. Observed cycle 8 minutes. "
            b"Monthly volume 3000 cases. Cash savings are not evidenced."
        ),
        source_kind="time_study",
        origin_class="raw_company_source",
        usage_policy="portfolio",
    )
    ctx.document(
        "rally",
        "revenue",
        filename="rally-monthly-revenue.txt",
        mime="text/plain",
        data=b"Company-reported net revenue for the latest month: 900000 USD.",
        source_kind="company_report",
        origin_class="raw_company_source",
        usage_policy="portfolio",
    )
    ctx.evidence(
        "rally",
        "meetings",
        document_key="meetings",
        kind="tagged_activity",
        locator={"kind": "csv", "column": "tagged"},
        excerpt="18 campaign-tagged meetings are recorded. The export does not contain recognized revenue.",
        origin_class="raw_company_source",
        sample_size="18 tagged meetings",
        collected_at=NOW - timedelta(days=3),
    )
    ctx.evidence(
        "rally",
        "time-study",
        document_key="time-study",
        kind="time_study",
        locator={"kind": "text", "section": "cycle time"},
        excerpt="Baseline 12 minutes, observed cycle 8 minutes, 3000 monthly cases. No budget change is attached.",
        origin_class="raw_company_source",
        sample_size="3000 monthly cases",
        collected_at=NOW - timedelta(days=3),
    )
    ctx.evidence(
        "rally",
        "revenue",
        document_key="revenue",
        kind="company_reported_revenue",
        locator={"kind": "text", "section": "monthly"},
        excerpt="Company-reported net revenue for the latest month is 900000 USD.",
        origin_class="raw_company_source",
        collected_at=NOW - timedelta(days=1),
        observed_end=NOW - timedelta(days=1),
    )
    ctx.db.flush()
    ctx.snapshot("rally", "initial", ["revenue"])
    ctx.snapshot("rally", "follow-on", ["meetings", "time-study"])
    ctx.run(
        "rally", "ainge", case_key="initial", phase="close", status="reviewed", owner="jordan.hale"
    )
    ctx.run(
        "rally",
        "ainge",
        case_key="follow-on",
        phase="independent",
        status="ready_for_review",
        owner="jordan.hale",
    )
    ctx.run(
        "rally",
        "mutombo",
        case_key="follow-on",
        phase="independent",
        status="ready_for_review",
        owner="jordan.hale",
    )
    ctx.db.flush()
    ctx.artifact(
        "rally",
        "initial-memo",
        case_key="initial",
        agent="ainge",
        phase="close",
        kind="ainge_report",
        status="reviewed",
        content={
            "summary": "Initial investment closed on a verified human record.",
            "findings": [],
            "missing_evidence": [],
            "human_questions": [],
            "proposed_actions": [],
            "limitations": [],
        },
    )
    ctx.artifact(
        "rally",
        "follow-ainge",
        case_key="follow-on",
        agent="ainge",
        phase="independent",
        kind="ainge_report",
        status="validated",
        content={
            "summary": "Follow-on case is separate from the original ownership record.",
            "findings": [],
            "missing_evidence": ["Follow-on terms are not final."],
            "human_questions": ["Does IC want to proceed, pass, or defer the follow-on?"],
            "proposed_actions": [],
            "limitations": ["Approving this case must not move Rally backward out of owned."],
        },
    )
    ctx.artifact(
        "rally",
        "follow-mutombo",
        case_key="follow-on",
        agent="mutombo",
        phase="independent",
        kind="independent_risk_report",
        status="sealed",
        sealed=True,
        content={
            "summary": "Follow-on dissent: incremental revenue is not evidenced by tagged meetings.",
            "findings": [
                _finding(
                    "Tagged meetings do not identify recognized revenue.",
                    kind="observation",
                    evidence=["meetings"],
                    slug="rally",
                )
            ],
            "missing_evidence": ["No incremental revenue study."],
            "human_questions": [],
            "proposed_actions": [],
            "limitations": ["Do not convert meetings into revenue."],
        },
    )
    ctx.db.flush()
    ctx.review(
        "rally",
        "initial-memo",
        reviewer="jordan.hale",
        notes="Closing memo matches the verified record.",
    )
    ctx.review(
        "rally",
        "follow-ainge",
        reviewer="priya.shah",
        notes="Follow-on memo leaves ownership in place.",
    )
    ctx.review(
        "rally",
        "follow-mutombo",
        reviewer="priya.shah",
        notes="Dissent correctly refuses to treat meetings as revenue.",
    )
    ctx.db.flush()
    initial_packet = ctx.packet(
        "rally", "initial", artifact_keys=["initial-memo"], status="decided"
    )
    ctx.packet(
        "rally",
        "follow-on",
        artifact_keys=["follow-ainge", "follow-mutombo"],
        status="frozen",
    )
    ctx.db.flush()
    ctx.db.add(
        Decision(
            id=fid("decision", "rally", "initial"),
            organization_id=ctx.org_id,
            workspace_id=ctx.ws("rally"),
            packet_id=initial_packet.id,
            packet_sha256=initial_packet.manifest_sha256,
            actor_id=fid("principal", "jordan.hale"),
            decision="approve",
            rationale="Initial investment approved on the frozen packet. This record stays attached to that packet hash.",
            decided_at=NOW - timedelta(days=50),
        )
    )
    ctx.db.flush()
    ctx.db.add(
        CloseRecord(
            id=fid("close", "rally", "initial"),
            organization_id=ctx.org_id,
            workspace_id=ctx.ws("rally"),
            case_id=fid("case", "rally", "initial"),
            document_id=fid("document", "rally", "closing"),
            effective_at=NOW - timedelta(days=40),
            actor_id=fid("principal", "jordan.hale"),
            verified_at=NOW - timedelta(days=40),
        )
    )
    hours = estimated_capacity_hours(
        baseline_minutes=Decimal("12"),
        future_minutes=Decimal("8"),
        monthly_cases=Decimal("3000"),
    )
    meetings = Initiative(
        id=fid("initiative", "rally", "meetings"),
        organization_id=ctx.org_id,
        workspace_id=ctx.ws("rally"),
        company_id=fid("company", "rally"),
        agent_name="stockton",
        goal="Record campaign-tagged meetings without treating them as revenue.",
        owner_id=fid("principal", "alex.chen"),
        status="active",
        baseline={"source": "tagged export"},
        measurement_plan="Count tagged meetings. Do not multiply by an assumed close rate.",
        costs={"currency": "USD", "amount": "0", "note": "No inventory was booked."},
    )
    study = Initiative(
        id=fid("initiative", "rally", "time-study"),
        organization_id=ctx.org_id,
        workspace_id=ctx.ws("rally"),
        company_id=fid("company", "rally"),
        agent_name="sloan",
        goal="Measure support cycle time and estimated capacity.",
        owner_id=fid("principal", "morgan.ellis"),
        status="active",
        baseline={"baseline_minutes": "12", "future_minutes": "8", "monthly_cases": "3000"},
        measurement_plan="Capacity stays estimated until a verified budget change exists.",
        costs={},
    )
    ctx.db.add(meetings)
    ctx.db.add(study)
    ctx.db.flush()
    ctx.db.add(
        ValueEntry(
            id=fid("value", "rally", "meetings"),
            organization_id=ctx.org_id,
            workspace_id=ctx.ws("rally"),
            initiative_id=meetings.id,
            metric="tagged_meetings",
            amount=Decimal("18"),
            unit="meetings",
            classification="observed",
            method="Count of campaign-tagged meetings in the export.",
            source_ids=[fid("evidence", "rally", "meetings")],
            period="latest",
        )
    )
    ctx.db.add(
        ValueEntry(
            id=fid("value", "rally", "cycle"),
            organization_id=ctx.org_id,
            workspace_id=ctx.ws("rally"),
            initiative_id=study.id,
            metric="support_cycle_time",
            amount=Decimal("8"),
            unit="minutes",
            classification="observed",
            method="Observed cycle time in the time study. Baseline was 12 minutes.",
            source_ids=[fid("evidence", "rally", "time-study")],
            period="latest",
        )
    )
    ctx.db.add(
        ValueEntry(
            id=fid("value", "rally", "capacity"),
            organization_id=ctx.org_id,
            workspace_id=ctx.ws("rally"),
            initiative_id=study.id,
            metric="capacity_released",
            amount=hours,
            unit="hours",
            classification="estimated",
            method="(12-8) minutes x 3000 monthly cases / 60. Estimated capacity, not cash saved.",
            source_ids=[fid("evidence", "rally", "time-study")],
            period="monthly",
        )
    )
    definition = MetricDefinition(
        id=fid("metric", "rally", "revenue"),
        organization_id=ctx.org_id,
        workspace_id=ctx.ws("rally"),
        slug="monthly_net_revenue",
        unit="USD",
        formula_version="v1",
        cadence="monthly",
        required=True,
        freshness_limit_days=40,
    )
    ctx.db.add(definition)
    ctx.db.flush()
    ctx.db.add(
        MetricObservation(
            id=fid("observation", "rally", "current"),
            organization_id=ctx.org_id,
            workspace_id=ctx.ws("rally"),
            definition_id=definition.id,
            period_start=NOW - timedelta(days=30),
            period_end=NOW - timedelta(days=1),
            value=Decimal("900000"),
            currency="USD",
            evidence_id=fid("evidence", "rally", "revenue"),
            completeness="complete",
            observed_at=NOW - timedelta(days=1),
        )
    )


def _company_court(ctx: _Ctx) -> None:
    ctx.company(
        "court",
        legal_name="Court Developer Tools, Inc.",
        website="https://court.example",
        stage="owned",
        owner="sam.okonkwo",
    )
    ctx.case(
        "court", "initial", case_type="initial", status="owned", owner="sam.okonkwo", due_at=None
    )
    ctx.db.flush()
    ctx.event(
        "court",
        "owned",
        case_key="initial",
        from_stage="closing",
        to_stage="owned",
        reason="Verified closing document recorded by an authorized person.",
        actor="jordan.hale",
        when=NOW - timedelta(days=80),
    )
    ctx.document(
        "court",
        "closing",
        filename="court-closing-record.txt",
        mime="text/plain",
        data=b"Fixture closing record for Court Developer Tools, Inc.",
        source_kind="closing",
        origin_class="human_reference",
        usage_policy="closing",
        ingestion_status="verified",
    )
    ctx.document(
        "court",
        "prior-report",
        filename="court-prior-quarter.txt",
        mime="text/plain",
        data=b"Prior quarter company-reported revenue was 4800000 USD. The current quarter report has not arrived.",
        source_kind="company_report",
        origin_class="raw_company_source",
        usage_policy="portfolio",
    )
    ctx.evidence(
        "court",
        "prior",
        document_key="prior-report",
        kind="company_reported_revenue",
        locator={"kind": "text", "section": "prior quarter"},
        excerpt="Prior quarter company-reported revenue was 4800000 USD.",
        origin_class="raw_company_source",
        collected_at=NOW - timedelta(days=100),
        observed_end=NOW - timedelta(days=110),
    )
    ctx.db.flush()
    ctx.snapshot("court", "initial", ["prior"])
    ctx.run(
        "court", "ainge", case_key="initial", phase="close", status="reviewed", owner="jordan.hale"
    )
    ctx.db.flush()
    ctx.artifact(
        "court",
        "initial-memo",
        case_key="initial",
        agent="ainge",
        phase="close",
        kind="ainge_report",
        status="reviewed",
        content={
            "summary": "Initial investment closed. Current-quarter reporting is a portfolio matter, not a reason to rewrite this memo.",
            "findings": [],
            "missing_evidence": [],
            "human_questions": [],
            "proposed_actions": [],
            "limitations": [],
        },
    )
    ctx.db.flush()
    ctx.review("court", "initial-memo", reviewer="jordan.hale", notes="Historical close memo.")
    packet = ctx.packet("court", "initial", artifact_keys=["initial-memo"], status="decided")
    ctx.db.flush()
    ctx.db.add(
        Decision(
            id=fid("decision", "court", "initial"),
            organization_id=ctx.org_id,
            workspace_id=ctx.ws("court"),
            packet_id=packet.id,
            packet_sha256=packet.manifest_sha256,
            actor_id=fid("principal", "jordan.hale"),
            decision="approve",
            rationale="Initial investment approved on the frozen packet.",
            decided_at=NOW - timedelta(days=90),
        )
    )
    ctx.db.flush()
    ctx.db.add(
        CloseRecord(
            id=fid("close", "court", "initial"),
            organization_id=ctx.org_id,
            workspace_id=ctx.ws("court"),
            case_id=fid("case", "court", "initial"),
            document_id=fid("document", "court", "closing"),
            effective_at=NOW - timedelta(days=80),
            actor_id=fid("principal", "jordan.hale"),
            verified_at=NOW - timedelta(days=80),
        )
    )
    definition = MetricDefinition(
        id=fid("metric", "court", "revenue"),
        organization_id=ctx.org_id,
        workspace_id=ctx.ws("court"),
        slug="quarterly_net_revenue",
        unit="USD",
        formula_version="v1",
        cadence="quarterly",
        required=True,
        freshness_limit_days=45,
    )
    ctx.db.add(definition)
    ctx.db.flush()
    ctx.db.add(
        MetricObservation(
            id=fid("observation", "court", "prior"),
            organization_id=ctx.org_id,
            workspace_id=ctx.ws("court"),
            definition_id=definition.id,
            period_start=NOW - timedelta(days=200),
            period_end=NOW - timedelta(days=110),
            value=Decimal("4800000"),
            currency="USD",
            evidence_id=fid("evidence", "court", "prior"),
            completeness="complete",
            observed_at=NOW - timedelta(days=100),
        )
    )
    ctx.db.add(
        MetricObservation(
            id=fid("observation", "court", "current"),
            organization_id=ctx.org_id,
            workspace_id=ctx.ws("court"),
            definition_id=definition.id,
            period_start=NOW - timedelta(days=90),
            period_end=NOW,
            value=None,
            currency="USD",
            completeness="missing",
            missing_reason="Quarterly board report was not received.",
            observed_at=None,
        )
    )
    event_id = fid("event", "court", "report-overdue")
    for subject in ("sam.okonkwo", "jordan.hale"):
        ctx.db.add(
            Notification(
                id=fid("notification", "court", subject),
                organization_id=ctx.org_id,
                workspace_id=ctx.ws("court"),
                principal_id=fid("principal", subject),
                event_id=event_id,
                severity="attention",
                title="Court reporting is overdue",
                body="The required quarterly revenue observation is missing. Health is unknown.",
                due_at=NOW - timedelta(days=1),
            )
        )


def _atlas_workbook() -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.title = "Cohort Retention"
    sheet["A1"] = "Fixture workbook. Not a live company."
    sheet["A13"] = "metric"
    sheet["D13"] = "value"
    rows = {
        14: ("starting_arr_usd", 1_000_000),
        15: ("contraction_usd", 90_000),
        16: ("churn_usd", 69_000),
        17: ("dollar_grr", 0.841),
        18: ("logo_grr", 0.916),
        19: ("reactivation", "excluded"),
        20: ("definition", "dollar GRR excludes expansion and reactivation"),
    }
    for index, (label, value) in rows.items():
        sheet[f"A{index}"] = label
        sheet[f"D{index}"] = value
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()
