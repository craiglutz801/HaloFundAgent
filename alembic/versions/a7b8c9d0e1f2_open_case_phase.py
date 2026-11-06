"""map an open case with an unknown phase from the company stage

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-11-05 21:45:00

"""

from typing import Sequence, Union

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE = r"""
UPDATE investment_cases ic
SET phase = CASE co.stage
  WHEN 'discovered' THEN 'sourcing'
  WHEN 'first_look' THEN 'screening'
  WHEN 'diligence' THEN 'due_diligence'
  WHEN 'ic_review' THEN 'investment_committee'
  WHEN 'term_sheet' THEN 'term_sheet'
  WHEN 'closing' THEN 'negotiation_closing'
  WHEN 'partner_review' THEN 'partner_review'
  ELSE ic.phase
END
FROM companies co
WHERE ic.company_id = co.id
  AND ic.organization_id = co.organization_id
  AND ic.workspace_id = co.workspace_id
  AND ic.phase = 'unknown'
  AND ic.status = 'open'
  AND ic.outcome = 'open'
  AND ic.on_hold = false
  AND co.stage IN (
    'discovered','first_look','diligence','ic_review','term_sheet',
    'closing','partner_review'
  );
"""

DOWNGRADE = r"""
SELECT 1;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
