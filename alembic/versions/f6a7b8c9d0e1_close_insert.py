"""allow an authorized close confirmation to insert a close record

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-05 21:40:00

"""

from typing import Sequence, Union

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE = r"""
DROP POLICY IF EXISTS close_records_insert ON close_records;
CREATE POLICY close_records_insert ON close_records
FOR INSERT WITH CHECK (halo_has_capability(organization_id, workspace_id, 'ic.decide'));

DO $halo_app_close$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'halo_app') THEN
    GRANT INSERT ON close_records TO halo_app;
  END IF;
END
$halo_app_close$;
"""

DOWNGRADE = r"""
DROP POLICY IF EXISTS close_records_insert ON close_records;
DO $halo_app_close_down$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'halo_app') THEN
    REVOKE INSERT ON close_records FROM halo_app;
  END IF;
END
$halo_app_close_down$;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
