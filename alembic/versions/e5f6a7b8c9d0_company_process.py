"""company process phase and agent assignments

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-05 21:30:00

"""

from typing import Sequence, Union

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE = r"""
ALTER TABLE companies DROP CONSTRAINT IF EXISTS ck_companies_stage;
ALTER TABLE companies ADD CONSTRAINT ck_companies_stage CHECK (
  stage IN (
    'discovered','first_look','diligence','ic_review','closing',
    'owned','exited','passed','paused','term_sheet','partner_review'
  )
);

ALTER TABLE investment_cases
  ADD COLUMN IF NOT EXISTS phase varchar(32) NOT NULL DEFAULT 'unknown',
  ADD COLUMN IF NOT EXISTS outcome varchar(16) NOT NULL DEFAULT 'open',
  ADD COLUMN IF NOT EXISTS on_hold boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS monitor boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS phase_entered_at timestamptz,
  ADD COLUMN IF NOT EXISTS outcome_at timestamptz,
  ADD COLUMN IF NOT EXISTS reason_code varchar(64) NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS reason_text text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS next_review_at timestamptz;

UPDATE investment_cases SET
  phase = CASE status
    WHEN 'discovered' THEN 'sourcing'
    WHEN 'first_look' THEN 'screening'
    WHEN 'diligence' THEN 'due_diligence'
    WHEN 'ic_review' THEN 'investment_committee'
    WHEN 'closing' THEN 'negotiation_closing'
    WHEN 'term_sheet' THEN 'term_sheet'
    WHEN 'partner_review' THEN 'partner_review'
    WHEN 'owned' THEN 'negotiation_closing'
    ELSE 'unknown'
  END,
  outcome = CASE
    WHEN status = 'owned' THEN 'portfolio'
    WHEN status = 'passed' THEN 'passed'
    ELSE 'open'
  END,
  on_hold = status = 'paused',
  phase_entered_at = COALESCE(phase_entered_at, created_at),
  outcome_at = CASE
    WHEN status IN ('owned', 'passed') THEN COALESCE(outcome_at, updated_at)
    ELSE outcome_at
  END;

ALTER TABLE investment_cases DROP CONSTRAINT IF EXISTS ck_cases_phase;
ALTER TABLE investment_cases ADD CONSTRAINT ck_cases_phase CHECK (
  phase IN (
    'sourcing','screening','partner_review','due_diligence',
    'investment_committee','term_sheet','negotiation_closing','unknown'
  )
);
ALTER TABLE investment_cases DROP CONSTRAINT IF EXISTS ck_cases_outcome;
ALTER TABLE investment_cases ADD CONSTRAINT ck_cases_outcome CHECK (
  outcome IN ('open','passed','portfolio')
);
CREATE INDEX IF NOT EXISTS ix_cases_company_phase ON investment_cases (company_id, phase, outcome);

CREATE TABLE IF NOT EXISTS agent_assignments (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL,
  workspace_id uuid NOT NULL,
  company_id uuid NOT NULL,
  agent_id varchar(32) NOT NULL,
  investment_process_id uuid,
  title varchar(200) NOT NULL,
  objective text NOT NULL DEFAULT '',
  status varchar(32) NOT NULL,
  owner_id uuid NOT NULL REFERENCES principals(id),
  created_by uuid NOT NULL REFERENCES principals(id),
  started_at timestamptz,
  completed_at timestamptz,
  last_activity_at timestamptz,
  blocked_reason text NOT NULL DEFAULT '',
  waiting_on text NOT NULL DEFAULT '',
  agent_config_version varchar(32) NOT NULL DEFAULT 'v1',
  supersedes_assignment_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT uq_assignments_scope_id UNIQUE (organization_id, workspace_id, id),
  CONSTRAINT ck_assignments_status CHECK (
    status IN ('queued','active','waiting_for_input','blocked','paused','completed','cancelled')
  ),
  CONSTRAINT fk_assignments_workspace FOREIGN KEY (organization_id, workspace_id)
    REFERENCES workspaces (organization_id, id),
  CONSTRAINT fk_assignments_company FOREIGN KEY (organization_id, workspace_id, company_id)
    REFERENCES companies (organization_id, workspace_id, id),
  CONSTRAINT fk_assignments_process FOREIGN KEY (organization_id, workspace_id, investment_process_id)
    REFERENCES investment_cases (organization_id, workspace_id, id)
);
CREATE INDEX IF NOT EXISTS ix_assignments_company_agent_status
  ON agent_assignments (company_id, agent_id, status);
CREATE INDEX IF NOT EXISTS ix_assignments_process ON agent_assignments (investment_process_id);

INSERT INTO agent_assignments (
  id, organization_id, workspace_id, company_id, agent_id, investment_process_id,
  title, objective, status, owner_id, created_by, started_at, completed_at,
  last_activity_at, blocked_reason, waiting_on, agent_config_version, created_at, updated_at
)
SELECT
  gen_random_uuid(),
  r.organization_id,
  r.workspace_id,
  ic.company_id,
  r.agent_name,
  r.case_id,
  initcap(r.agent_name) || ' project',
  COALESCE(NULLIF(string_agg(DISTINCT r.status_detail, ' '), ''), 'Imported from an existing run'),
  CASE
    WHEN bool_or(r.status = 'running') THEN 'active'
    WHEN bool_and(r.status IN ('reviewed', 'succeeded')) THEN 'completed'
    WHEN bool_or(r.status = 'failed') AND NOT bool_or(r.status = 'running') THEN 'blocked'
    WHEN bool_and(r.status = 'queued') THEN 'queued'
    ELSE 'active'
  END,
  (array_agg(r.owner_id ORDER BY r.created_at))[1],
  (array_agg(r.owner_id ORDER BY r.created_at))[1],
  min(r.created_at),
  CASE WHEN bool_and(r.status IN ('reviewed', 'succeeded')) THEN max(r.updated_at) ELSE NULL END,
  max(r.updated_at),
  CASE WHEN bool_or(r.status = 'failed') THEN 'A run failed. The project stays open for retry.' ELSE '' END,
  '',
  'v1',
  min(r.created_at),
  now()
FROM agent_runs r
JOIN investment_cases ic ON ic.id = r.case_id
WHERE NOT EXISTS (
  SELECT 1 FROM agent_assignments a
  WHERE a.investment_process_id = r.case_id AND a.agent_id = r.agent_name
    AND a.title = initcap(r.agent_name) || ' project'
)
GROUP BY r.organization_id, r.workspace_id, ic.company_id, r.agent_name, r.case_id;

UPDATE agent_assignments a
SET status = 'completed',
    completed_at = COALESCE(a.completed_at, now())
WHERE a.agent_id = 'xavier'
  AND a.company_id IN (SELECT id FROM companies WHERE display_name = 'Atlas');

INSERT INTO agent_assignments (
  id, organization_id, workspace_id, company_id, agent_id, investment_process_id,
  title, objective, status, owner_id, created_by, started_at, last_activity_at,
  blocked_reason, waiting_on, agent_config_version, created_at, updated_at
)
SELECT
  gen_random_uuid(),
  c.organization_id,
  c.workspace_id,
  c.id,
  'mutombo',
  ic.id,
  'Reference challenge',
  'Test founder-introduced references as its own project. This does not open comparison grants.',
  'active',
  c.owner_id,
  c.owner_id,
  now(),
  now(),
  '',
  '',
  'v1',
  now(),
  now()
FROM companies c
JOIN investment_cases ic ON ic.company_id = c.id AND ic.case_type = 'initial'
WHERE c.display_name = 'Atlas'
  AND NOT EXISTS (
    SELECT 1 FROM agent_assignments a
    WHERE a.company_id = c.id AND a.agent_id = 'mutombo' AND a.title = 'Reference challenge'
  );

ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS assignment_id uuid;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS heartbeat_at timestamptz;
UPDATE agent_runs SET heartbeat_at = updated_at WHERE status = 'running' AND heartbeat_at IS NULL;
UPDATE agent_runs r
SET assignment_id = a.id
FROM agent_assignments a
WHERE r.assignment_id IS NULL
  AND a.investment_process_id = r.case_id
  AND a.agent_id = r.agent_name
  AND a.title = initcap(r.agent_name) || ' project';

DO $runs_assignment$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'fk_runs_assignment'
  ) THEN
    ALTER TABLE agent_runs
      ADD CONSTRAINT fk_runs_assignment
      FOREIGN KEY (organization_id, workspace_id, assignment_id)
      REFERENCES agent_assignments (organization_id, workspace_id, id);
  END IF;
END
$runs_assignment$;
CREATE INDEX IF NOT EXISTS ix_runs_assignment_created ON agent_runs (assignment_id, created_at DESC);

ALTER TABLE agent_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_assignments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS scoped_read ON agent_assignments;
CREATE POLICY scoped_read ON agent_assignments
  FOR SELECT USING (halo_can_read_workspace(organization_id, workspace_id));

DO $halo_app_assignments$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'halo_app') THEN
    GRANT SELECT ON agent_assignments TO halo_app;
  END IF;
END
$halo_app_assignments$;
"""

DOWNGRADE = r"""
ALTER TABLE agent_runs DROP CONSTRAINT IF EXISTS fk_runs_assignment;
DROP INDEX IF EXISTS ix_runs_assignment_created;
ALTER TABLE agent_runs DROP COLUMN IF EXISTS assignment_id;
ALTER TABLE agent_runs DROP COLUMN IF EXISTS heartbeat_at;
DROP TABLE IF EXISTS agent_assignments;
ALTER TABLE investment_cases DROP CONSTRAINT IF EXISTS ck_cases_phase;
ALTER TABLE investment_cases DROP CONSTRAINT IF EXISTS ck_cases_outcome;
DROP INDEX IF EXISTS ix_cases_company_phase;
ALTER TABLE investment_cases
  DROP COLUMN IF EXISTS phase,
  DROP COLUMN IF EXISTS outcome,
  DROP COLUMN IF EXISTS on_hold,
  DROP COLUMN IF EXISTS monitor,
  DROP COLUMN IF EXISTS phase_entered_at,
  DROP COLUMN IF EXISTS outcome_at,
  DROP COLUMN IF EXISTS reason_code,
  DROP COLUMN IF EXISTS reason_text,
  DROP COLUMN IF EXISTS next_review_at;
ALTER TABLE companies DROP CONSTRAINT IF EXISTS ck_companies_stage;
ALTER TABLE companies ADD CONSTRAINT ck_companies_stage CHECK (
  stage IN (
    'discovered','first_look','diligence','ic_review','closing',
    'owned','exited','passed','paused'
  )
);
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
