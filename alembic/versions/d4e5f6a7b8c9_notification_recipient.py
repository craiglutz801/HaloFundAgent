"""notifications are visible to the recipient

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-02 21:20:00

"""

from typing import Sequence, Union

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP POLICY IF EXISTS scoped_read ON notifications")
    op.execute(
        """
        CREATE POLICY notifications_read ON notifications
        FOR SELECT USING (
          principal_id = halo_current_principal()
          AND halo_can_read_workspace(organization_id, workspace_id)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS notifications_read ON notifications")
    op.execute(
        """
        CREATE POLICY scoped_read ON notifications
        FOR SELECT USING (halo_can_read_workspace(organization_id, workspace_id))
        """
    )
