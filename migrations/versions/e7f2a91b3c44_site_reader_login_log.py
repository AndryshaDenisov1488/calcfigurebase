"""site reader login log (judge site-access password)

Revision ID: e7f2a91b3c44
Revises: c4e90122aa02
Create Date: 2026-05-11

"""
from alembic import op
import sqlalchemy as sa


revision = 'e7f2a91b3c44'
down_revision = 'c4e90122aa02'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'site_reader_login_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('client_ip', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_site_reader_login_log_client_ip', 'site_reader_login_log', ['client_ip'], unique=False)
    op.create_index('ix_site_reader_login_log_created_at', 'site_reader_login_log', ['created_at'], unique=False)


def downgrade():
    op.drop_index('ix_site_reader_login_log_created_at', table_name='site_reader_login_log')
    op.drop_index('ix_site_reader_login_log_client_ip', table_name='site_reader_login_log')
    op.drop_table('site_reader_login_log')
