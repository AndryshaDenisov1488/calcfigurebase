"""pair member details

Revision ID: a91c7d42f610
Revises: e7f2a91b3c44
Create Date: 2026-08-30

"""
from alembic import op
import sqlalchemy as sa


revision = 'a91c7d42f610'
down_revision = 'e7f2a91b3c44'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('athlete') as batch:
        batch.add_column(sa.Column('primary_external_id', sa.String(length=50), nullable=True))
        batch.add_column(sa.Column('primary_first_name', sa.String(length=100), nullable=True))
        batch.add_column(sa.Column('primary_last_name', sa.String(length=100), nullable=True))
        batch.add_column(sa.Column('primary_patronymic', sa.String(length=100), nullable=True))
        batch.add_column(sa.Column('primary_birth_date', sa.Date(), nullable=True))
        batch.add_column(sa.Column('primary_gender', sa.String(length=1), nullable=True))
        batch.add_column(sa.Column('partner_external_id', sa.String(length=50), nullable=True))
        batch.add_column(sa.Column('partner_first_name', sa.String(length=100), nullable=True))
        batch.add_column(sa.Column('partner_last_name', sa.String(length=100), nullable=True))
        batch.add_column(sa.Column('partner_patronymic', sa.String(length=100), nullable=True))
        batch.add_column(sa.Column('partner_birth_date', sa.Date(), nullable=True))
        batch.add_column(sa.Column('partner_gender', sa.String(length=1), nullable=True))
        batch.create_index('ix_athlete_primary_external_id', ['primary_external_id'], unique=False)
        batch.create_index('ix_athlete_primary_birth_date', ['primary_birth_date'], unique=False)
        batch.create_index('ix_athlete_partner_external_id', ['partner_external_id'], unique=False)
        batch.create_index('ix_athlete_partner_birth_date', ['partner_birth_date'], unique=False)


def downgrade():
    with op.batch_alter_table('athlete') as batch:
        batch.drop_index('ix_athlete_partner_birth_date')
        batch.drop_index('ix_athlete_partner_external_id')
        batch.drop_index('ix_athlete_primary_birth_date')
        batch.drop_index('ix_athlete_primary_external_id')
        batch.drop_column('partner_gender')
        batch.drop_column('partner_birth_date')
        batch.drop_column('partner_patronymic')
        batch.drop_column('partner_last_name')
        batch.drop_column('partner_first_name')
        batch.drop_column('partner_external_id')
        batch.drop_column('primary_gender')
        batch.drop_column('primary_birth_date')
        batch.drop_column('primary_patronymic')
        batch.drop_column('primary_last_name')
        batch.drop_column('primary_first_name')
        batch.drop_column('primary_external_id')
