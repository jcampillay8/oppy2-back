"""add Title Field to AvatarDefinition

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-07 11:41:35.223232

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Creamos la columna permitiendo NULL inicialmente para no romper con filas existentes
    op.add_column(
        'avatar_definitions', 
        sa.Column('title', sa.String(length=150), nullable=True), 
        schema='chat'
    )

    # 2. Llenamos los registros antiguos con un valor por defecto (puedes cambiar 'Escenario' por lo que quieras)
    op.execute("UPDATE chat.avatar_definitions SET title = 'Escenario de Práctica' WHERE title IS NULL")

    # 3. Ahora que todos tienen un valor, aplicamos la restricción NOT NULL
    op.alter_column(
        'avatar_definitions', 
        'title', 
        nullable=False, 
        schema='chat'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('avatar_definitions', 'title', schema='chat')


