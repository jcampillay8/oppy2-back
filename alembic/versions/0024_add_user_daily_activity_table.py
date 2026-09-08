"""Add user_daily_activity table

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-26 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0024'
down_revision: Union[str, None] = '0023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS chat.user_daily_activity (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES chat.users(id),
            course_type VARCHAR(30) NOT NULL DEFAULT 'ielts',
            activity_date DATE NOT NULL,
            response_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            CONSTRAINT uq_user_course_date UNIQUE (user_id, course_type, activity_date)
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chat.user_daily_activity;")
