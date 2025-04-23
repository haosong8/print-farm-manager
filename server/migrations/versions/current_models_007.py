"""Drop printer_id column from product_components table

Revision ID: 20250325_prod_comp_drop_printer_id
Revises: 20250325_prod_comp_fix
Create Date: 2025-03-25 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = '20250325_drop_printer_id'
down_revision = '20250325_prod_comp_fix'
branch_labels = None
depends_on = None

def column_exists(table_name, column_name):
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = inspector.get_columns(table_name)
    return any(col['name'] == column_name for col in columns)

def upgrade():
    with op.batch_alter_table('product_components') as batch_op:
        # If the "printer_id" column exists in product_components,
        # drop it so that the table schema matches the current model.
        if column_exists('product_components', 'printer_id'):
            batch_op.drop_column('printer_id')

def downgrade():
    # In the downgrade, re-add the "printer_id" column.
    # You might want to set appropriate constraints or a default value;
    # here we re-add it as non-nullable without a default.
    with op.batch_alter_table('product_components') as batch_op:
        if not column_exists('product_components', 'printer_id'):
            batch_op.add_column(
                sa.Column('printer_id', sa.Integer(), nullable=False)
            )
