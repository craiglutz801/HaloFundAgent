-- Row-level security, authorization helpers, and immutability triggers.
-- Functions that read authorization metadata are SECURITY DEFINER, owned by the
-- migration role, with a fixed search_path. They return booleans or session
-- identifiers. They do not return evidence content.

CREATE OR REPLACE FUNCTION halo_current_principal() RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('halo.principal_id', true), '')::uuid;
$$;

CREATE OR REPLACE FUNCTION halo_shares_org(p_org uuid) RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM organization_memberships
    WHERE principal_id = halo_current_principal()
      AND organization_id = p_org
      AND status = 'active'
  );
$$;

CREATE OR REPLACE FUNCTION halo_can_read_workspace(p_org uuid, p_ws uuid) RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM principals p
    JOIN organization_memberships om ON om.principal_id = p.id
    JOIN workspace_memberships wm
      ON wm.principal_id = p.id
     AND wm.organization_id = om.organization_id
    WHERE p.id = halo_current_principal()
      AND p.active
      AND p.kind = 'user'
      AND om.organization_id = p_org
      AND om.status = 'active'
      AND wm.workspace_id = p_ws
      AND wm.status = 'active'
      AND (wm.expires_at IS NULL OR wm.expires_at > now())
  );
$$;

CREATE OR REPLACE FUNCTION halo_has_capability(p_org uuid, p_ws uuid, p_cap text) RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM principals p
    JOIN organization_memberships om ON om.principal_id = p.id
    JOIN workspace_memberships wm
      ON wm.principal_id = p.id
     AND wm.organization_id = om.organization_id
    WHERE p.id = halo_current_principal()
      AND p.active
      AND p.kind = 'user'
      AND om.organization_id = p_org
      AND om.status = 'active'
      AND wm.workspace_id = p_ws
      AND wm.status = 'active'
      AND (wm.expires_at IS NULL OR wm.expires_at > now())
      AND p_cap = ANY (wm.capabilities)
  );
$$;

CREATE OR REPLACE FUNCTION halo_can_read_evidence(p_org uuid, p_ws uuid, p_evidence uuid)
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_principal uuid := halo_current_principal();
  v_kind text;
  v_status text;
  v_origin text;
  v_phase text := NULLIF(current_setting('halo.run_phase', true), '');
BEGIN
  IF v_principal IS NULL THEN
    RETURN false;
  END IF;
  SELECT kind INTO v_kind FROM principals WHERE id = v_principal AND active;
  IF v_kind IS NULL THEN
    RETURN false;
  END IF;
  SELECT status, origin_class INTO v_status, v_origin
  FROM evidence_records
  WHERE id = p_evidence
    AND organization_id = p_org
    AND workspace_id = p_ws;
  IF v_status IS DISTINCT FROM 'active' THEN
    RETURN false;
  END IF;
  IF v_kind = 'service'
     AND v_phase = 'independent'
     AND v_origin IN ('peer_agent_output', 'investment_conclusion') THEN
    RETURN false;
  END IF;
  IF v_kind = 'user' THEN
    RETURN halo_can_read_workspace(p_org, p_ws);
  END IF;
  IF v_kind = 'service' THEN
    IF v_phase IS NULL THEN
      RETURN false;
    END IF;
    RETURN EXISTS (
      SELECT 1
      FROM run_grants g
      JOIN agent_runs r
        ON r.id = g.run_id
       AND r.organization_id = g.organization_id
       AND r.workspace_id = g.workspace_id
      WHERE g.organization_id = p_org
        AND g.workspace_id = p_ws
        AND r.owner_id = v_principal
        AND g.revoked_at IS NULL
        AND (g.expires_at IS NULL OR g.expires_at > now())
        AND g.allowed_operation = 'read'
        AND g.phase = v_phase
        AND (
          (g.resource_kind = 'evidence' AND g.resource_id = p_evidence)
          OR (
            g.resource_kind = 'snapshot'
            AND EXISTS (
              SELECT 1 FROM snapshot_evidence se
              WHERE se.snapshot_id = g.resource_id
                AND se.evidence_id = p_evidence
            )
          )
        )
    );
  END IF;
  RETURN false;
END;
$$;

CREATE OR REPLACE FUNCTION halo_open_fixture_session(
  p_principal uuid,
  p_token_hash text,
  p_ttl_seconds integer
) RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF current_database() NOT LIKE '%fixture%' OR current_database() LIKE '%live%' THEN
    RAISE EXCEPTION 'fixture session is disabled';
  END IF;
  IF NOT EXISTS (
    SELECT 1
    FROM principals p
    JOIN organization_memberships om ON om.principal_id = p.id
    JOIN organizations o ON o.id = om.organization_id
    WHERE p.id = p_principal
      AND p.kind = 'user'
      AND p.active
      AND om.status = 'active'
      AND o.mode = 'fixture'
  ) THEN
    RAISE EXCEPTION 'principal is not an active fixture member';
  END IF;
  INSERT INTO sessions (id, token_hash, principal_id, expires_at, last_seen_at)
  VALUES (
    gen_random_uuid(),
    p_token_hash,
    p_principal,
    now() + make_interval(secs => p_ttl_seconds),
    now()
  );
END;
$$;

CREATE OR REPLACE FUNCTION halo_resolve_session(p_token_hash text) RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  found uuid;
BEGIN
  SELECT principal_id INTO found
  FROM sessions
  WHERE token_hash = p_token_hash
    AND revoked_at IS NULL
    AND expires_at > now();
  IF found IS NOT NULL THEN
    UPDATE sessions SET last_seen_at = now() WHERE token_hash = p_token_hash;
  END IF;
  RETURN found;
END;
$$;

CREATE OR REPLACE FUNCTION halo_revoke_session(p_token_hash text) RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  UPDATE sessions
  SET revoked_at = now()
  WHERE token_hash = p_token_hash
    AND revoked_at IS NULL;
END;
$$;

REVOKE ALL ON FUNCTION halo_current_principal() FROM PUBLIC;
REVOKE ALL ON FUNCTION halo_shares_org(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION halo_can_read_workspace(uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION halo_has_capability(uuid, uuid, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION halo_can_read_evidence(uuid, uuid, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION halo_open_fixture_session(uuid, text, integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION halo_resolve_session(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION halo_revoke_session(text) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION halo_current_principal() TO halo_app;
GRANT EXECUTE ON FUNCTION halo_shares_org(uuid) TO halo_app;
GRANT EXECUTE ON FUNCTION halo_can_read_workspace(uuid, uuid) TO halo_app;
GRANT EXECUTE ON FUNCTION halo_has_capability(uuid, uuid, text) TO halo_app;
GRANT EXECUTE ON FUNCTION halo_can_read_evidence(uuid, uuid, uuid) TO halo_app;
GRANT EXECUTE ON FUNCTION halo_open_fixture_session(uuid, text, integer) TO halo_app;
GRANT EXECUTE ON FUNCTION halo_resolve_session(text) TO halo_app;
GRANT EXECUTE ON FUNCTION halo_revoke_session(text) TO halo_app;

CREATE OR REPLACE FUNCTION halo_reject_direct_stage_update() RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  transition_id uuid;
BEGIN
  IF NEW.stage IS NOT DISTINCT FROM OLD.stage THEN
    RETURN NEW;
  END IF;
  BEGIN
    transition_id := NULLIF(current_setting('halo.stage_transition_id', true), '')::uuid;
  EXCEPTION WHEN others THEN
    RAISE EXCEPTION 'direct stage update rejected';
  END;
  IF transition_id IS NULL THEN
    RAISE EXCEPTION 'direct stage update rejected; missing stage transition';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM stage_events se
    WHERE se.id = transition_id
      AND se.company_id = NEW.id
      AND se.organization_id = NEW.organization_id
      AND se.workspace_id = NEW.workspace_id
      AND se.to_stage = NEW.stage
      AND se.from_stage = OLD.stage
  ) THEN
    RAISE EXCEPTION 'direct stage update rejected; transition does not match';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS companies_stage_guard ON companies;
CREATE TRIGGER companies_stage_guard
BEFORE UPDATE ON companies
FOR EACH ROW EXECUTE FUNCTION halo_reject_direct_stage_update();

CREATE OR REPLACE FUNCTION halo_reviews_bind_artifact() RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  actual text;
BEGIN
  SELECT a.sha256 INTO actual
  FROM artifacts a
  WHERE a.id = NEW.artifact_id
    AND a.organization_id = NEW.organization_id
    AND a.workspace_id = NEW.workspace_id;
  IF actual IS NULL OR actual <> NEW.artifact_sha256 THEN
    RAISE EXCEPTION 'review artifact_sha256 does not match artifact version';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS reviews_bind_artifact ON reviews;
CREATE TRIGGER reviews_bind_artifact
BEFORE INSERT ON reviews
FOR EACH ROW EXECUTE FUNCTION halo_reviews_bind_artifact();

CREATE OR REPLACE FUNCTION halo_decisions_bind_packet() RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  actual text;
BEGIN
  SELECT manifest_sha256 INTO actual
  FROM ic_packets
  WHERE id = NEW.packet_id
    AND organization_id = NEW.organization_id
    AND workspace_id = NEW.workspace_id;
  IF actual IS NULL OR actual <> NEW.packet_sha256 THEN
    RAISE EXCEPTION 'decision packet_sha256 does not match packet manifest';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS decisions_bind_packet ON decisions;
CREATE TRIGGER decisions_bind_packet
BEFORE INSERT ON decisions
FOR EACH ROW EXECUTE FUNCTION halo_decisions_bind_packet();

CREATE OR REPLACE FUNCTION halo_artifacts_immutable() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.sha256 IS DISTINCT FROM OLD.sha256 OR NEW.content_json IS DISTINCT FROM OLD.content_json THEN
    RAISE EXCEPTION 'artifact bytes are immutable';
  END IF;
  IF NEW.kind IS DISTINCT FROM OLD.kind OR NEW.version IS DISTINCT FROM OLD.version THEN
    RAISE EXCEPTION 'artifact identity is immutable';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS artifacts_immutable ON artifacts;
CREATE TRIGGER artifacts_immutable
BEFORE UPDATE ON artifacts
FOR EACH ROW EXECUTE FUNCTION halo_artifacts_immutable();

CREATE OR REPLACE FUNCTION halo_packets_manifest_immutable() RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.manifest_sha256 IS DISTINCT FROM OLD.manifest_sha256
     OR NEW.version IS DISTINCT FROM OLD.version
     OR NEW.case_id IS DISTINCT FROM OLD.case_id THEN
    RAISE EXCEPTION 'packet manifest is immutable';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS packets_manifest_immutable ON ic_packets;
CREATE TRIGGER packets_manifest_immutable
BEFORE UPDATE ON ic_packets
FOR EACH ROW EXECUTE FUNCTION halo_packets_manifest_immutable();

CREATE OR REPLACE FUNCTION halo_close_record_requirements() RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_case_type text;
  v_company_stage text;
BEGIN
  SELECT c.case_type, co.stage INTO v_case_type, v_company_stage
  FROM investment_cases c
  JOIN companies co
    ON co.id = c.company_id
   AND co.organization_id = c.organization_id
   AND co.workspace_id = c.workspace_id
  WHERE c.id = NEW.case_id
    AND c.organization_id = NEW.organization_id
    AND c.workspace_id = NEW.workspace_id;
  IF v_case_type IS NULL THEN
    RAISE EXCEPTION 'close record case is not in this workspace';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM documents d
    WHERE d.id = NEW.document_id
      AND d.organization_id = NEW.organization_id
      AND d.workspace_id = NEW.workspace_id
      AND d.ingestion_status = 'verified'
      AND d.source_kind = 'closing'
  ) THEN
    RAISE EXCEPTION 'close record requires a verified closing document';
  END IF;
  IF NOT EXISTS (
    SELECT 1
    FROM ic_packets p
    JOIN decisions dec
      ON dec.packet_id = p.id
     AND dec.decision = 'approve'
     AND dec.packet_sha256 = p.manifest_sha256
    WHERE p.case_id = NEW.case_id
      AND p.organization_id = NEW.organization_id
      AND p.workspace_id = NEW.workspace_id
  ) THEN
    RAISE EXCEPTION 'close record requires an approved decision on this case';
  END IF;
  IF v_case_type <> 'initial' AND v_company_stage IS DISTINCT FROM 'owned' THEN
    RAISE EXCEPTION 'follow-on close cannot create company ownership';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS close_records_requirements ON close_records;
CREATE TRIGGER close_records_requirements
BEFORE INSERT ON close_records
FOR EACH ROW EXECUTE FUNCTION halo_close_record_requirements();

-- Enable and force RLS. Table owners do not bypass FORCE ROW LEVEL SECURITY.
-- The migration role has BYPASSRLS. The application role does not.

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations FORCE ROW LEVEL SECURITY;
ALTER TABLE principals ENABLE ROW LEVEL SECURITY;
ALTER TABLE principals FORCE ROW LEVEL SECURITY;
ALTER TABLE organization_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_memberships FORCE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE idempotency_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE idempotency_keys FORCE ROW LEVEL SECURITY;
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspaces FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS organizations_read ON organizations;
CREATE POLICY organizations_read ON organizations
FOR SELECT USING (halo_shares_org(id));

DROP POLICY IF EXISTS principals_read ON principals;
CREATE POLICY principals_read ON principals
FOR SELECT USING (
  id = halo_current_principal()
  OR EXISTS (
    SELECT 1
    FROM organization_memberships mine
    JOIN organization_memberships theirs
      ON theirs.organization_id = mine.organization_id
    WHERE mine.principal_id = halo_current_principal()
      AND mine.status = 'active'
      AND theirs.principal_id = principals.id
      AND theirs.status = 'active'
  )
);

DROP POLICY IF EXISTS org_memberships_read ON organization_memberships;
CREATE POLICY org_memberships_read ON organization_memberships
FOR SELECT USING (halo_shares_org(organization_id));

DROP POLICY IF EXISTS idempotency_own ON idempotency_keys;
CREATE POLICY idempotency_own ON idempotency_keys
FOR ALL
USING (principal_id = halo_current_principal() AND halo_shares_org(organization_id))
WITH CHECK (principal_id = halo_current_principal() AND halo_shares_org(organization_id));

DROP POLICY IF EXISTS workspaces_read ON workspaces;
CREATE POLICY workspaces_read ON workspaces
FOR SELECT USING (halo_can_read_workspace(organization_id, id));

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'workspace_memberships',
    'companies',
    'investment_cases',
    'stage_events',
    'documents',
    'evidence_snapshots',
    'snapshot_evidence',
    'fund_bundle_items',
    'agent_runs',
    'run_grants',
    'artifacts',
    'artifact_dependencies',
    'artifact_source_scopes',
    'findings',
    'finding_evidence',
    'concerns',
    'concern_dispositions',
    'reviews',
    'ic_packets',
    'decisions',
    'close_records',
    'metric_definitions',
    'metric_observations',
    'initiatives',
    'value_entries',
    'playbooks',
    'report_releases',
    'budget_reservations',
    'provider_calls',
    'audit_events',
    'outbox_events',
    'activity_outcomes',
    'notifications'
  ]
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS scoped_read ON %I', t);
    EXECUTE format(
      'CREATE POLICY scoped_read ON %I FOR SELECT USING (halo_can_read_workspace(organization_id, workspace_id))',
      t
    );
  END LOOP;
END $$;

ALTER TABLE evidence_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_records FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS evidence_read ON evidence_records;
CREATE POLICY evidence_read ON evidence_records
FOR SELECT USING (halo_can_read_evidence(organization_id, workspace_id, id));

DROP POLICY IF EXISTS decisions_insert ON decisions;
CREATE POLICY decisions_insert ON decisions
FOR INSERT WITH CHECK (halo_has_capability(organization_id, workspace_id, 'ic.decide'));

DROP POLICY IF EXISTS reviews_insert ON reviews;
CREATE POLICY reviews_insert ON reviews
FOR INSERT WITH CHECK (halo_has_capability(organization_id, workspace_id, 'artifact.review'));

DROP POLICY IF EXISTS dispositions_insert ON concern_dispositions;
CREATE POLICY dispositions_insert ON concern_dispositions
FOR INSERT WITH CHECK (halo_has_capability(organization_id, workspace_id, 'concern.disposition'));

DROP POLICY IF EXISTS stage_events_insert ON stage_events;
CREATE POLICY stage_events_insert ON stage_events
FOR INSERT WITH CHECK (
  halo_has_capability(organization_id, workspace_id, 'ic.decide')
  OR halo_has_capability(organization_id, workspace_id, 'case.submit_ic')
  OR halo_has_capability(organization_id, workspace_id, 'close.record')
);

DROP POLICY IF EXISTS companies_update ON companies;
CREATE POLICY companies_update ON companies
FOR UPDATE
USING (
  halo_has_capability(organization_id, workspace_id, 'ic.decide')
  OR halo_has_capability(organization_id, workspace_id, 'case.submit_ic')
  OR halo_has_capability(organization_id, workspace_id, 'close.record')
)
WITH CHECK (
  halo_has_capability(organization_id, workspace_id, 'ic.decide')
  OR halo_has_capability(organization_id, workspace_id, 'case.submit_ic')
  OR halo_has_capability(organization_id, workspace_id, 'close.record')
);

DROP POLICY IF EXISTS cases_update ON investment_cases;
CREATE POLICY cases_update ON investment_cases
FOR UPDATE
USING (
  halo_has_capability(organization_id, workspace_id, 'ic.decide')
  OR halo_has_capability(organization_id, workspace_id, 'case.submit_ic')
)
WITH CHECK (
  halo_has_capability(organization_id, workspace_id, 'ic.decide')
  OR halo_has_capability(organization_id, workspace_id, 'case.submit_ic')
);

DROP POLICY IF EXISTS concerns_update ON concerns;
CREATE POLICY concerns_update ON concerns
FOR UPDATE
USING (halo_has_capability(organization_id, workspace_id, 'concern.disposition'))
WITH CHECK (halo_has_capability(organization_id, workspace_id, 'concern.disposition'));

DROP POLICY IF EXISTS packets_update ON ic_packets;
CREATE POLICY packets_update ON ic_packets
FOR UPDATE
USING (halo_has_capability(organization_id, workspace_id, 'ic.decide'))
WITH CHECK (halo_has_capability(organization_id, workspace_id, 'ic.decide'));

DROP POLICY IF EXISTS audit_insert ON audit_events;
CREATE POLICY audit_insert ON audit_events
FOR INSERT WITH CHECK (halo_can_read_workspace(organization_id, workspace_id));

DROP POLICY IF EXISTS outbox_insert ON outbox_events;
CREATE POLICY outbox_insert ON outbox_events
FOR INSERT WITH CHECK (halo_can_read_workspace(organization_id, workspace_id));

DROP POLICY IF EXISTS notifications_insert ON notifications;
CREATE POLICY notifications_insert ON notifications
FOR INSERT WITH CHECK (halo_can_read_workspace(organization_id, workspace_id));

DROP POLICY IF EXISTS notifications_update ON notifications;
CREATE POLICY notifications_update ON notifications
FOR UPDATE
USING (principal_id = halo_current_principal())
WITH CHECK (principal_id = halo_current_principal());

GRANT USAGE ON SCHEMA public TO halo_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO halo_app;
GRANT INSERT ON
  reviews,
  decisions,
  concern_dispositions,
  stage_events,
  audit_events,
  outbox_events,
  notifications,
  idempotency_keys
TO halo_app;
GRANT UPDATE ON
  companies,
  investment_cases,
  concerns,
  ic_packets,
  notifications
TO halo_app;
GRANT UPDATE (response_json, status_code) ON idempotency_keys TO halo_app;

REVOKE ALL ON sessions FROM halo_app;
REVOKE UPDATE, DELETE ON
  decisions,
  reviews,
  concern_dispositions,
  evidence_snapshots,
  snapshot_evidence,
  audit_events,
  stage_events
FROM halo_app;
