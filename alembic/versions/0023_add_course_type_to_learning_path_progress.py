"""Add course_type column to learning_path_progress table

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-25 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0023'
down_revision: Union[str, None] = '0022'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE chat.learning_path_progress ADD COLUMN IF NOT EXISTS course_type VARCHAR(30) NOT NULL DEFAULT 'standard';"
    )


def downgrade() -> None:
    op.drop_column('learning_path_progress', 'course_type', schema='chat')
