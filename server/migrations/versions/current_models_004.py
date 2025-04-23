"""Add due_date column to products

Revision ID: 20250325_due_date
Revises: 20250325_cam_cfg
Create Date: 2025-03-25 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250325_due_date'
down_revision = '20250325_cam_cfg'
branch_labels = None
depends_on = None

def upgrade():
    # Add the due_date column to the products table.
    # We provide a temporary server_default (for example, '1970-01-01 00:00:00')
    # so that existing rows are not rejected. Then, we remove the default.
    op.add_column('products',
        sa.Column('due_date', sa.DateTime(), nullable=False, server_default='1970-01-01 00:00:00')
    )
    op.alter_column('products', 'due_date', server_default=None)

def downgrade():
    op.drop_column('products', 'due_date')
