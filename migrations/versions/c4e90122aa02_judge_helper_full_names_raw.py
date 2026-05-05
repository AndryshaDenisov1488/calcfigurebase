"""judge helper audit full names text

Revision ID: c4e90122aa02
Revises: b8f3a21c9e01
Create Date: 2026-05-06

"""
from alembic import op
import sqlalchemy as sa


revision = 'c4e90122aa02'
down_revision = 'b8f3a21c9e01'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('judge_helper_free_audit') as batch:
        batch.add_column(sa.Column('names_raw', sa.Text(), nullable=True))
        batch.add_column(
            sa.Column('input_truncated', sa.Boolean(), nullable=False, server_default='0'),
        )


def downgrade():
    with op.batch_alter_table('judge_helper_free_audit') as batch:
        batch.drop_column('input_truncated')
        batch.drop_column('names_raw')
