"""fixture roster function

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-11-02 21:05:00

"""

from typing import Sequence, Union

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SQL = """
CREATE OR REPLACE FUNCTION halo_fixture_roster()
RETURNS TABLE(id uuid, display_name text, email text, role text)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF current_database() NOT LIKE '%fixture%' OR current_database() LIKE '%live%' THEN
    RAISE EXCEPTION 'fixture roster is disabled';
  END IF;
  RETURN QUERY
  SELECT p.id, p.display_name::text, p.email::text, om.role::text
  FROM principals p
  JOIN organization_memberships om ON om.principal_id = p.id
  JOIN organizations o ON o.id = om.organization_id
  WHERE p.kind = 'user'
    AND p.active
    AND p.oidc_subject NOT LIKE 'service:%'
    AND om.status = 'active'
    AND o.mode = 'fixture'
  ORDER BY p.display_name;
END;
$$;

REVOKE ALL ON FUNCTION halo_fixture_roster() FROM PUBLIC;
DO $halo_app_roster$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'halo_app') THEN
    GRANT EXECUTE ON FUNCTION halo_fixture_roster() TO halo_app;
  END IF;
END
$halo_app_roster$;
"""


def upgrade() -> None:
    op.execute(SQL)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS halo_fixture_roster()")
