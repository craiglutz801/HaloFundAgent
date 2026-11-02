"""row level security and immutability triggers

Revision ID: b1c2d3e4f5a6
Revises: 7e948b237324
Create Date: 2026-11-02 20:45:00

"""

from pathlib import Path
from typing import Sequence, Union

from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "7e948b237324"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    sql = Path(__file__).with_name("0002_security.sql").read_text()
    op.execute(sql)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS close_records_requirements ON close_records")
    op.execute("DROP TRIGGER IF EXISTS packets_manifest_immutable ON ic_packets")
    op.execute("DROP TRIGGER IF EXISTS artifacts_immutable ON artifacts")
    op.execute("DROP TRIGGER IF EXISTS decisions_bind_packet ON decisions")
    op.execute("DROP TRIGGER IF EXISTS reviews_bind_artifact ON reviews")
    op.execute("DROP TRIGGER IF EXISTS companies_stage_guard ON companies")
