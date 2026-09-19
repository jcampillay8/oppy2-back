"""Add vocab_leftover to user_daily_activity

Revision ID: 0025
Revises: 0024
Create Date: 2026-09-19 10:51:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0025'
down_revision: Union[str, None] = '0024'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE chat.user_daily_activity 
        ADD COLUMN IF NOT EXISTS vocab_leftover INTEGER NOT NULL DEFAULT 0;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE chat.user_daily_activity 
        DROP COLUMN IF EXISTS vocab_leftover;
    """)
