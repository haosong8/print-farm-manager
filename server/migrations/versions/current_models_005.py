"""Add required_material column to product_components

Revision ID: 20250325_prod_comp_req_mat
Revises: 20250325_due_date
Create Date: 2025-03-25 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250325_prod_comp_req_mat'
down_revision = '20250325_due_date'
branch_labels = None
depends_on = None

def upgrade():
    # Add the required_material column to the product_components table.
    # We set a temporary server_default so that existing rows receive a value.
    op.add_column('product_components',
        sa.Column('required_material', sa.String(100), nullable=False, server_default='PLA')
    )
    # Remove the temporary default.
    op.alter_column('product_components', 'required_material', server_default=None)

def downgrade():
    op.drop_column('product_components', 'required_material')
