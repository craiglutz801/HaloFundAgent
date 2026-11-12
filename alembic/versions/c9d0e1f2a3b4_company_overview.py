"""company overview stays on the company

Revision ID: c9d0e1f2a3b4
Revises: a7b8c9d0e1f2
Create Date: 2026-11-12 18:20:00

"""

from typing import Sequence, Union

from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE = r"""
ALTER TABLE companies
  ADD COLUMN IF NOT EXISTS industry varchar(160) NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS summary text NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS revenue_note varchar(240) NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS headcount_note varchar(120) NOT NULL DEFAULT '',
  ADD COLUMN IF NOT EXISTS trajectory text NOT NULL DEFAULT '';
"""

DOWNGRADE = r"""
ALTER TABLE companies
  DROP COLUMN IF EXISTS trajectory,
  DROP COLUMN IF EXISTS headcount_note,
  DROP COLUMN IF EXISTS revenue_note,
  DROP COLUMN IF EXISTS summary,
  DROP COLUMN IF EXISTS industry;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
