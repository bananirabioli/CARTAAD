"""laboratorio: facts.status (propuesto | activo | descartado) and facts.source_quote

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-02 21:30:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0010'
down_revision: str | None = '0009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('facts') as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=False, server_default='activo'))
        batch_op.add_column(sa.Column('source_quote', sa.Text(), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('source_page', sa.Integer(), nullable=True))
        batch_op.create_index('ix_facts_status', ['status'])


def downgrade() -> None:
    with op.batch_alter_table('facts') as batch_op:
        batch_op.drop_index('ix_facts_status')
        batch_op.drop_column('source_page')
        batch_op.drop_column('source_quote')
        batch_op.drop_column('status')
