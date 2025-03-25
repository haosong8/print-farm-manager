"""Add filament_total column to gcodes

Revision ID: 20250325_add_filament_total
Revises: None
Create Date: 2025-03-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250325_add_filament_total'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('gcodes', sa.Column('filament_total', sa.Float(), nullable=True))

def downgrade():
    op.drop_column('gcodes', 'filament_total')
