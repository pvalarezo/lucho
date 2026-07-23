"""add_daily_digest_enabled_to_user_profile

Revision ID: 43f1a001ba39
Revises: c5b0797cba0b
Create Date: 2026-07-23 10:20:39.827546

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '43f1a001ba39'
down_revision: Union[str, Sequence[str], None] = 'c5b0797cba0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user_profiles",
        sa.Column(
            "daily_digest_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("user_profiles", "daily_digest_enabled")
