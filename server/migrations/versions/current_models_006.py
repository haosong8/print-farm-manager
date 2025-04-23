"""Fix product_components table by dropping old gcode_id column and ensuring required_material exists

Revision ID: 20250325_prod_comp_fix
Revises: 20250325_prod_comp_req_mat
Create Date: 2025-03-25 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '20250325_prod_comp_fix'
down_revision = '20250325_prod_comp_req_mat'
branch_labels = None
depends_on = None

def column_exists(table_name, column_name):
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = inspector.get_columns(table_name)
    return any(col['name'] == column_name for col in columns)

def upgrade():
    with op.batch_alter_table('product_components') as batch_op:
        # Drop the old 'gcode_id' column if it exists.
        if column_exists('product_components', 'gcode_id'):
            batch_op.drop_column('gcode_id')

        # Add the 'required_material' column if it does not exist.
        if not column_exists('product_components', 'required_material'):
            batch_op.add_column(
                sa.Column('required_material', sa.String(100), nullable=False, server_default='PLA')
            )
            # Remove the temporary default
            batch_op.alter_column('required_material', server_default=None)
        else:
            # If the column exists, ensure it is non-nullable and has a default if needed.
            batch_op.alter_column('required_material', nullable=False, server_default='PLA')
            batch_op.alter_column('required_material', server_default=None)

def downgrade():
    with op.batch_alter_table('product_components') as batch_op:
        batch_op.drop_column('required_material')
        # Optionally, re-add the old 'gcode_id' column if needed.
        # Example:
        # batch_op.add_column(sa.Column('gcode_id', sa.Integer(), nullable=False))
