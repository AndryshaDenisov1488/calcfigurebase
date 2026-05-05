"""judge helper free audit table

Revision ID: b8f3a21c9e01
Revises: 814525e701e1
Create Date: 2026-05-06

"""
from alembic import op
import sqlalchemy as sa


revision = 'b8f3a21c9e01'
down_revision = '814525e701e1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'judge_helper_free_audit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('remote_addr', sa.String(length=45), nullable=True),
        sa.Column('reader_logged_in', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('parsed_names_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('input_char_len', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('input_preview', sa.Text(), nullable=True),
        sa.Column('result_has_free', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('result_no_free', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('result_fio_only', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('result_not_found', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_judge_helper_free_audit_created_at', 'judge_helper_free_audit', ['created_at'])
    op.create_index('ix_judge_helper_free_audit_reader_logged_in', 'judge_helper_free_audit', ['reader_logged_in'])


def downgrade():
    op.drop_index('ix_judge_helper_free_audit_reader_logged_in', table_name='judge_helper_free_audit')
    op.drop_index('ix_judge_helper_free_audit_created_at', table_name='judge_helper_free_audit')
    op.drop_table('judge_helper_free_audit')
